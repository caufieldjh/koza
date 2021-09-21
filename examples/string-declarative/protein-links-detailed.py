import re
import uuid

from koza.biolink.model import Protein, PairwiseGeneToGeneInteraction
from koza.manager.data_provider import inject_row, inject_translation_table
from koza.manager.data_collector import write

source_name = 'protein-links-detailed'

row = inject_row(source_name)
translation_table = inject_translation_table()

protein_a = Protein(category="biolink:Protein", id='ENSEMBL:' + re.sub(r'\d+\.', '', row['protein1']))
protein_b = Protein(category="biolink:Protein", id='ENSEMBL:' + re.sub(r'\d+\.', '', row['protein2']))

pairwise_gene_to_gene_interaction = PairwiseGeneToGeneInteraction(
    category="biolink:PairwiseGeneToGeneInteraction",
    id="uuid:" + str(uuid.uuid1()),
    subject=protein_a,
    object=protein_b,
    predicate="biolink:interacts_with",
    relation = translation_table.global_table['interacts with'],
)

write(source_name, protein_a, protein_b, pairwise_gene_to_gene_interaction)
