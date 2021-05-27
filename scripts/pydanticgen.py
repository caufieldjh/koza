#!/usr/bin/env python3

"""
A pydantic generator based on the LinkML python generator

Some key differences:

- pydantic dataclasses instead of vanilla dataclasses,
  see https://pydantic-docs.helpmanual.io/usage/dataclasses/

- UriOrCurie is replaced with a Curie type as a goal to represent
  all identifiers as curies

- Identifier types are removed, eg Union[str, EntityId] is replaced with
  Curie

- Category attribute is inferred via class variables and the type hierarchy
    - Note that for id and type, and sometimes other attributes these
      are overridden anyway in the child class.  I think this happens when
      a slot if given a new description in the child class, linkml gives
      the a slot a unique name (child_class_id, child_class_type) to
      attach the updated description, need to check this with Harold

- Type conversions, convers scalars to lists for Union[someScalar, List[someScalar]]

What parts of the schema are left out (and expected downstream)

- Required attributes, eg id, should be checked or supplied downstream


Downstream code will also need to handle nested types to be compliant with
Neo4J's data model.  Nested types will need to be converted to some primitive type
(string, number, or lists of a primitive type)


Why pydantic over standard dataclasses?

  - Validation on both initializing and setting of variables

  - Built in type coercion (this is perhaps a con as Union types are handled in odd ways for now)
    see https://github.com/samuelcolvin/pydantic/issues/1423
    https://github.com/samuelcolvin/pydantic/pull/2092

  - Built in parsing of json or yaml into nested models (ie when attributes are reference types)

  - Supported by FastAPI

"""

from pathlib import Path
from typing import List, Optional, TextIO, Tuple, Union

import typer
from linkml.generators import PYTHON_GEN_VERSION
from linkml.generators.pythongen import PythonGenerator
from linkml.utils.formatutils import be, camelcase, split_line, wrapped_annotation
from linkml.utils.mergeutils import alias_root
from linkml_model.meta import ClassDefinition, ClassDefinitionName, SchemaDefinition, SlotDefinition


class PydanticGen(PythonGenerator):
    """
    A pydantic dataclass generator

    """

    generatorname = Path(__file__).name
    generatorversion = PYTHON_GEN_VERSION

    def __init__(self, schema: Union[str, TextIO, SchemaDefinition], **kwargs):
        super().__init__(
            schema=schema,
            format='py',
            genmeta=False,
            gen_classvars=False,
            gen_slots=False,
            **kwargs,
        )

    # Overriden methods

    def _sort_classes(self, clist: List[ClassDefinition]) -> List[ClassDefinition]:
        """
        sort classes such that if C is a child of P then C appears after P in the list

        Overriden method include mixin classes
        """
        clist = list(clist)
        slist = []  # sorted
        while len(clist) > 0:
            can_add = False
            for i in range(len(clist)):
                candidate = clist[i]
                can_add = False
                if candidate.is_a:
                    candidates = [candidate.is_a] + candidate.mixins
                else:
                    candidates = candidate.mixins
                if not candidates:
                    can_add = True
                else:
                    if set(candidates) <= set([p.name for p in slist]):
                        can_add = True
                if can_add:
                    slist = slist + [candidate]
                    del clist[i]
                    break
            if not can_add:
                raise ValueError(
                    f'could not find suitable element in {clist} that does not ref {slist}'
                )
        return slist

    def gen_schema(self) -> str:
        split_descripton = '\n#              '.join(
            split_line(be(self.schema.description), split_len=100)
        )
        head = (
            f'''# Auto generated from {self.schema.source_file} by {self.generatorname} version: {self.generatorversion}
# Generation date: {self.schema.generation_date}
# Schema: {self.schema.name}
#'''
            if self.schema.generation_date
            else ''
        )

        return f'''{head}
# id: {self.schema.id}
# description: {split_descripton}
# license: {be(self.schema.license)}

from collections import namedtuple
from dataclasses import field
import datetime
import inspect
from typing import Optional, List, Union, Dict, ClassVar, Any

from pydantic.dataclasses import dataclass
from pydantic import validator, constr

metamodel_version = "{self.schema.metamodel_version}"

# Type Aliases
Unit = Union[int, float]
LabelType = str
IriType = constr(regex=r'^http')
Curie = constr(regex=r'^[a-zA-Z_]?[a-zA-Z_0-9-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*[A-Za-z0-9_]*$')
NarrativeText = str
XSDDate = datetime.date
TimeType = datetime.time
SymbolType = str
FrequencyValue = str
PercentageFrequencyValue = float
BiologicalSequence = str
Quotient = float

# Classes
{self.gen_classdefs()}

'''

    def gen_classdef(self, cls: ClassDefinition) -> str:
        """ Generate python definition for class cls """

        parent_class_and_mixins = ""

        if cls.is_a:
            parents = [cls.is_a]
            if cls.mixins:
                parents = parents + cls.mixins
            parent_class_and_mixins = ', '.join(
                [self.formatted_element_name(parent, True) for parent in parents]
            )
            parent_class_and_mixins = f'({parent_class_and_mixins})'
        elif cls.mixins:
            # Seems fine but more curious if this ever happens
            self.logger.warning(f"class {cls.name} has mixins {cls.mixins} but no parent")
            mixins = ', '.join([self.formatted_element_name(mixin, True) for mixin in cls.mixins])
            parent_class_and_mixins = f'({mixins})'

        slotdefs = self.gen_class_variables(cls)

        entity_post_init = (
            f'\n\t{self._get_entity_post_init()}'
            if self.class_or_type_name(cls.name) == 'Entity'
            else ''
        )

        wrapped_description = (
            f'\n\t"""\n\t{wrapped_annotation(be(cls.description))}\n\t"""'
            if be(cls.description)
            else ''
        )

        pydantic_validators = self.gen_pydantic_validators(cls)

        return (
            ('\n@dataclass(config=PydanticConfig)' if slotdefs else '')
            + f'\nclass {self.class_or_type_name(cls.name)}'
            + parent_class_and_mixins
            + f':{wrapped_description}\n'
            + f'{self.gen_inherited_slots(cls)}'
            + f'{self.gen_pydantic_classvars(cls)}'
            + (f'\t{slotdefs}\n' if slotdefs else '')
            + f'{pydantic_validators}'
            + f'{entity_post_init}'
            + (
                f'\n\tpass'
                if (
                    not self.gen_inherited_slots(cls)
                    and not self.gen_pydantic_classvars(cls)
                    and not slotdefs
                    and not entity_post_init
                    and not pydantic_validators
                )
                else ''
            )
            + '\n'
        )

    def gen_class_variables(self, cls: ClassDefinition) -> str:
        """
        Generate the variable declarations for a dataclass.

        Overriden to only generate variables for domain slots

        :param cls: class containing variables to be rendered in inheritence hierarchy
        :return: variable declarations for target class and its ancestors
        """
        initializers = []

        domain_slots = self.domain_slots(cls)

        if cls.name == 'entity':
            slot_variables = self._slot_iter(
                cls, lambda slot: slot.name in ['id', 'type', 'category']
            )
            initializers += [self.gen_class_variable(cls, slot, False) for slot in slot_variables]

        # Required or key slots with default values
        slot_variables = self._slot_iter(
            cls,
            lambda slot: slot.required
            and slot in domain_slots
            and alias_root(self.schema, slot.name) not in ['id', 'type', 'category'],
        )
        initializers += [self.gen_class_variable(cls, slot, False) for slot in slot_variables]

        # Followed by everything else
        slot_variables = self._slot_iter(
            cls,
            lambda slot: not slot.required
            and slot in domain_slots
            and alias_root(self.schema, slot.name) not in ['id', 'type', 'category'],
        )
        initializers += [self.gen_class_variable(cls, slot, False) for slot in slot_variables]

        return '\n\t'.join(initializers)

    def range_cardinality(
        self, slot: SlotDefinition, cls: Optional[ClassDefinition], positional_allowed: bool
    ) -> Tuple[str, Optional[str]]:
        """
        Overriding to switch empty_list() and empty_dict() to

        field(default_factory={list | dict})
        """
        positional_allowed = False  # Force everything to be tag values
        slotname = self.slot_name(slot.name)

        range_type, parent_type, _ = self.class_reference_type(slot, cls)
        pkey = self.class_identifier(slot.range)
        # Special case, inlined, identified range
        if pkey and slot.inlined and slot.multivalued:
            base_key = self.gen_class_reference(
                self.class_identifier_path(slot.range, False), slotname
            )
            num_elements = len(self.schema.classes[slot.range].slots)
            dflt = None if slot.required and positional_allowed else 'field(default_factory=dict)'
            if num_elements == 1:
                if slot.required:
                    return f'Union[List[{base_key}], Dict[{base_key}, {range_type}]]', dflt
                else:
                    return (
                        f'Optional[Union[List[{base_key}], Dict[{base_key}, {range_type}]]]',
                        dflt,
                    )
            else:
                if slot.required:
                    return f'Union[Dict[{base_key}, {range_type}], List[{range_type}]]', dflt
                else:
                    return (
                        f'Optional[Union[Dict[{base_key}, {range_type}], List[{range_type}]]]',
                        dflt,
                    )

        # All other cases
        if slot.multivalued:
            if slot.required:
                return f'Union[{range_type}, List[{range_type}]]', (
                    None if positional_allowed else 'None'
                )
            else:
                return (
                    f'Optional[Union[{range_type}, List[{range_type}]]]',
                    'field(default_factory=list)',
                )
        elif slot.required:
            return range_type, (None if positional_allowed else 'None')
        else:
            return f'Optional[{range_type}]', 'None'

    def class_reference_type(
        self, slot: SlotDefinition, cls: Optional[ClassDefinition]
    ) -> Tuple[str, str, str]:
        """
        Return the type of a slot referencing a class

        :param slot: slot to be typed
        :param cls: owning class.  Used for generating key references
        :return: Python class reference type, most proximal type, most proximal type name
        """

        slotname = self.slot_name(slot.name)

        rangelist = (
            self.class_identifier_path(cls, False)
            if slot.key or slot.identifier
            else self.slot_range_path(slot)
        )
        prox_type = self.slot_range_path(slot)[-1].rsplit('.')[-1]
        prox_type_name = rangelist[-1]

        # Quote forward references - note that enums always gen at the end
        if slot.range in self.schema.enums or (
            cls
            and slot.inlined
            and slot.range in self.schema.classes
            and self.forward_reference(slot.range, cls.name)
        ):
            rangelist[-1] = f'"{rangelist[-1]}"'

        # return str(self.gen_class_reference(rangelist)), prox_type, prox_type_name
        return str(self.gen_class_reference(rangelist, slotname)), prox_type, prox_type_name

    @staticmethod
    def gen_class_reference(rangelist: List[str], slot_name: str = None) -> str:
        """
        Return a basic or a union type depending on the number of elements in range list

        Instead of the pythongen version which uses the base type and a special
        Id type, eg
        Entity -> str, EntityID

        We have a union of str, Curie, and the class, eg
        Entity -> str, Curie, Entity

        TODO clean this up

        :param rangelist: List of types from distal to proximal
        :return:
        """
        base = rangelist[0].split('.')[-1]

        if (
            slot_name
            in [
                'id',
                'provided_by',
                'has_qualitative_value',
                'category',
                'subclass_of',
                'has_input',
                'has_output',
                'has_constituent',
                'enabled_by',
            ]
            or ('URIorCURIE' in rangelist and rangelist[-1] != 'IriType')
        ):
            # id is here to override {ClassName}Id
            # The rest are due to import order errors in self._sort_classes
            # From changing {ClassName}Id to {ClassName}

            # Check if base is str? for now just assume it is
            class_ref = "Curie"

        elif 'Entity' in rangelist:
            class_ref = f"Union[Curie, {rangelist[-1]}]" if len(rangelist) > 1 else base
        elif 'Bool' == rangelist[-1]:
            class_ref = 'bool'
        else:
            if len(rangelist) > 1 and rangelist[-1] == 'IriType':
                class_ref = 'IriType'
            else:
                class_ref = f"Union[{base}, {rangelist[-1]}]" if len(rangelist) > 1 else base

        return class_ref

    def class_identifier_path(
        self, cls_or_clsname: Union[str, ClassDefinition], force_non_key: bool
    ) -> List[str]:
        """
        Return the path closure to a class identifier if the class has a key and force_non_key is false otherwise
        return a dictionary closure.

        :param cls_or_clsname: class definition
        :param force_non_key: True means inlined even if the class has a key
        :return: path
        """
        cls = (
            cls_or_clsname
            if isinstance(cls_or_clsname, ClassDefinition)
            else self.schema.classes[ClassDefinitionName(cls_or_clsname)]
        )

        # Determine whether the class has a key
        identifier_slot = None
        if not force_non_key:
            identifier_slot = self.class_identifier(cls)

        # No key or inlined, its closure is a dictionary
        if identifier_slot is None:
            # return ['dict', self.class_or_type_name(cls.name)]
            # Not certain why this is dict and if it's a model smell
            # We want everything to be str, Curie, List, or another Dataclass in the model
            return ['str', self.class_or_type_name(cls.name)]

        # Override class name + self.aliased_slot_name
        # For example, instead of EntityId, which means nothing for the pydantic gen
        # use the dataclass itself Entity
        # pathname = camelcase(cls.name + ' ' + self.aliased_slot_name(identifier_slot))
        pathname = camelcase(cls.name)
        if cls.is_a:
            parent_identifier_slot = self.class_identifier(cls.is_a)
            if parent_identifier_slot:
                return self.class_identifier_path(cls.is_a, False) + [pathname]
        return self.slot_range_path(identifier_slot) + [pathname]

    def domain_slots(self, cls: ClassDefinition) -> List[SlotDefinition]:
        """
        Return all slots in the class definition that are owned by the class

        Overridden to remove domain_of mixin(s) slots so we can use the mixin
        slot inheritance instead
        """
        return [
            slot
            for slot in [self.schema.slots[sn] for sn in cls.slots]
            if cls.name in slot.domain_of
        ]

    # New Methods

    def gen_pydantic_classvars(self, cls: ClassDefinition) -> str:
        """
        Generate classvars specific to the pydantic dataclasses
        """

        vars = []

        if not (cls.mixin or cls.abstract):
            vars.append(f'_category: ClassVar[str] = "{camelcase(cls.name)}"')

        required_slots = self._slot_iter(cls, lambda slot: slot.required)

        required_slots_fmt = ',\n'.join(
            [f'\t\t"{self.slot_name(slot.name)}"' for slot in required_slots]
        )

        if required_slots_fmt:
            vars.append(f'_required_attributes: ClassVar[List[str]] = [\n{required_slots_fmt}\n\t]')

        if vars:
            ret_val = "\n\t" + "\n\t".join(vars) + "\n"
        else:
            ret_val = ""

        return ret_val

    @staticmethod
    def _get_entity_post_init() -> str:
        """
        Post init for entity for inferring categories from the
        classes in its method resolution order

        requires a special classvar _category which is excluded
        from mixins
        """
        return '''
    def __post_init__(self):
        # Initialize default categories if not set
        # by traversing the MRO chain
        if not self.category:
            self.category = list(
                {
                    super_class._category
                    for super_class in inspect.getmro(type(self))
                    if hasattr(super_class, '_category')
                }
            )
        '''

    def gen_predicate_named_tuple(self) -> str:
        """
        Creates a named tuple of all biolink predicates
        which are slots that descend from 'related to'
        :return:
        """
        predicates = []
        for slot in self.schema.slots.values():
            if 'related to' in self.ancestors(slot):
                predicates.append(slot.name)

        predicates = [pred.replace(' ', '_') for pred in sorted(predicates)]
        formatted_predicates = '\n'.join([f"    '{pred}'," for pred in predicates])

        return f'''

predicates = [
{formatted_predicates}
]

predicate = namedtuple('biolink_predicate', predicates)(
    *['biolink:' + predicate for predicate in predicates]
)

'''

    def gen_pydantic_validators(self, cls) -> str:
        """

        :param cls:
        :return:
        """
        validators = []

        if cls.name == 'entity':
            validators.append(self._gen_id_namespace_validator(cls.id_prefixes))

        for slot in self.domain_slots(cls):
            slotname = self.slot_name(slot.name)
            if slot.multivalued:
                validators.append(
                    f'_convert_{slotname}_to_list = convert_scalar_to_list("{slotname}")'
                )

        if validators:
            ret_val = "\n\t# Validators\n\t" + "\n\t".join(validators) + "\n"
        else:
            ret_val = ""

        return ret_val

    @staticmethod
    def _gen_id_namespace_validator(namespaces: List[str], slotname=None) -> str:
        """
        :param namespaces:
        :return:
        """
        namespaces_fmt = ',\n'.join([f'\t\t\t\t"{ns}"' for ns in namespaces])
        if not slotname:
            slotname = 'id'

        return f'''
    @validator('{slotname}')
    def check_{slotname}_prefix(cls, id):
        return check_curie_prefix(
            id,
            [
{namespaces_fmt}
            ],
        )
'''


def main(yamlfile: str):
    pydantic_config = Path(__file__).parent / 'pydantic_config.py'
    with open(pydantic_config, 'r') as py_conf:
        for line in py_conf:
            print(line.rstrip())
    pydantic_generator = PydanticGen(yamlfile)
    print(pydantic_generator.serialize())
    print(pydantic_generator.gen_predicate_named_tuple())


if __name__ == "__main__":
    typer.run(main)
