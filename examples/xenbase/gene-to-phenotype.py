import uuid
from dataclasses import asdict

from koza.biolink.model import Gene, PhenotypicFeature, GeneToPhenotypicFeatureAssociation
from koza.manager.data_provider import inject_row
from koza.manager.data_collector import write

source_name = 'gene-to-phenotype'

row = inject_row(source_name)

gene = Gene(category="biolink:Gene", id='Xenbase:' + row['SUBJECT'])

phenotype = PhenotypicFeature(category="biolink:PhenotypicFeature", id=row['OBJECT'])

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
