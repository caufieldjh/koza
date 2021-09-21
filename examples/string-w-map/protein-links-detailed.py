import uuid

from koza.biolink.model import Gene, PairwiseGeneToGeneInteraction
from koza.manager.data_provider import inject_row, inject_translation_table, inject_map
from koza.manager.data_collector import write

source_name = 'protein-links-detailed'

row = inject_row(source_name)
translation_table = inject_translation_table()
entrez_2_string = inject_map('entrez_2_string')

gene_a = Gene(category="biolink:Gene", id='NCBIGene:' + entrez_2_string[row['protein1']]['entrez'])
gene_b = Gene(category="biolink:Gene", id='NCBIGene:' + entrez_2_string[row['protein2']]['entrez'])

pairwise_gene_to_gene_interaction = PairwiseGeneToGeneInteraction(
    category="biolink:PairwiseGeneToGeneInteraction",
    id="uuid:" + str(uuid.uuid1()),
    subject=gene_a.id,
    object=gene_b.id,
    predicate="biolink:interacts_with",
    relation=translation_table.global_table['interacts with'],
)

write(source_name, gene_a, gene_b, pairwise_gene_to_gene_interaction)
