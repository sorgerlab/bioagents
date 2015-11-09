# DDA stands for disease-drug agent whose task is to
# search for targets known to be implicated in a 
# certain disease and to look for drugs that are known 
# to affect that target directly or indirectly.

import re
import rdflib
from bioagents import cbio_client
import warnings
import indra.bel.processor

class DDA:
    def __init__(self):
        # Build an initial set of substitution statements
        bel_corpus = '../data/large_corpus_direct_subs.rdf'
        g = rdflib.Graph()
        g.parse(bel_corpus, format='nt')
        bp = indra.bel.processor.BelProcessor(g)
        bp.get_activating_subs()
        self.sub_statements = bp.statements

    def get_mutation_effect(self, protein_name, amino_acid_change):
        match = re.match(r'([A-Z])([0-9]+)([A-Z])', amino_acid_change)
        matches = match.groups()
        wt_residue = matches[0]
        pos = matches[1]
        sub_residue = matches[2]

        for stmt in self.sub_statements:
            if stmt.monomer.name == protein_name and\
                stmt.wt_residue == wt_residue and\
                stmt.pos == pos and\
                stmt.sub_residue == sub_residue:
                print 'Match found, activity: %s' % stmt.activity
                return stmt.activity
        return None

    
    def get_mutation_statistics(self, disease_name_filter, mutation_type):
        study_ids = cbio_client. get_cancer_studies(disease_name_filter)
        if not study_ids:
            warnings.warn('No study found for "%s"' % disease_name_filter)
            return None
        gene_list_str = self._get_gene_list_str()
        mutation_dict = {}
        num_case = 0
        for study_id in study_ids:
            num_case += cbio_client.get_num_sequenced(study_id)
            mutations = cbio_client.get_mutations(study_id, gene_list_str, 
                                                  mutation_type)
            for m in mutations:
                try:
                    mutation_dict[m] += 1.0
                except KeyError:
                    mutation_dict[m] = 1.0
        # Normalize entries
        for k, v in mutation_dict.iteritems():
            mutation_dict[k] /= num_case

        return mutation_dict

    def _get_gene_list_str(self):
        gene_list_str = \
            ','.join([','.join(v) for v in self.gene_lists.values()])
        return gene_list_str

    gene_lists = {
        'rtk_signaling':
        ["EGFR", "ERBB2", "ERBB3", "ERBB4", "PDGFA", "PDGFB",
        "PDGFRA", "PDGFRB", "KIT", "FGF1", "FGFR1", "IGF1",
        "IGF1R", "VEGFA", "VEGFB", "KDR"],
        'pi3k_signaling':
        ["PIK3CA", "PIK3R1", "PIK3R2", "PTEN", "PDPK1", "AKT1",
        "AKT2", "FOXO1", "FOXO3", "MTOR", "RICTOR", "TSC1", "TSC2",
        "RHEB", "AKT1S1", "RPTOR", "MLST8"],
        'mapk_signaling':
        ["KRAS", "HRAS", "BRAF", "RAF1", "MAP3K1", "MAP3K2", "MAP3K3", 
        "MAP3K4", "MAP3K5", "MAP2K1", "MAP2K2", "MAP2K3", "MAP2K4", 
        "MAP2K5", "MAPK1", "MAPK3", "MAPK4", "MAPK6", "MAPK7", "MAPK8", 
        "MAPK9", "MAPK12", "MAPK14", "DAB2", "RASSF1", "RAB25"]
        }

if __name__ == '__main__':
    mutation_dict = get_mutation_statistics('pancreatic', 'missense')
