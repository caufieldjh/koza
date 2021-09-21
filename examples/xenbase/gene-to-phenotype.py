import uuid
from dataclasses import asdict

from koza.biolink.model import Gene, PhenotypicFeature, GeneToPhenotypicFeatureAssociation
from koza.manager.data_provider import inject_row
from koza.manager.data_collector import write

source_name = 'gene-to-phenotype'

row = inject_row(source_name)

gene = Gene(id='Xenbase:' + row['SUBJECT'], category="biolink:Gene")

phenotype = PhenotypicFeature(id=row['OBJECT'], category="biolink:PhenotypicFeature")

association = GeneToPhenotypicFeatureAssociation(
    category="biolink:GeneToPhenotypicFeatureAssociation",
    id="uuid:" + str(uuid.uuid1()),
    subject=gene,
    predicate="biolink:has_phenotype",
    object=phenotype,
    relation=row['RELATION'].replace('_', ':')
)

if row['SOURCE']:
    association.publications = [row['SOURCE']]

write(source_name, gene, association, phenotype)
