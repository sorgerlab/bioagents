# DTDA stands for disease-target-drug agent whose task is to
# search for targets known to be implicated in a 
# certain disease and to look for drugs that are known 
# to affect that target directly or indirectly.

import re
import os
import rdflib
import sqlite3
import numpy
from bioagents import cbio_client
import warnings
import indra.bel.processor

class DTDA:
    def __init__(self):
        data_dir = os.path.dirname(os.path.realpath(__file__)) + '/data/'
        # Build an initial set of substitution statements
        bel_corpus = data_dir + 'large_corpus_direct_subs.rdf'
        g = rdflib.Graph()
        g.parse(bel_corpus, format='nt')
        bp = indra.bel.processor.BelProcessor(g)
        bp.get_activating_subs()
        self.sub_statements = bp.statements
        # Load a database of drug targets
        self.drug_db = sqlite3.connect(data_dir + 'drug_targets.db', 
            check_same_thread=False)
   
    def __del__(self):
        self.drug_db.close()

    def is_nominal_drug_target(self, drug_name, target_name):
        '''
        Return True if the drug targets the target, and False if not
        '''
        res = self.drug_db.execute('SELECT nominal_target FROM agent '
                           'WHERE synonyms LIKE "%%%s%%" '
                           'OR name LIKE "%%%s%%"' % (drug_name, drug_name)).fetchall()
        for r in res:
            if r[0] == target_name:
                return True
        return False

    def find_target_drug(self, target_name):
        '''
        Find all the drugs that nominally target the target.
        '''
        res = self.drug_db.execute('SELECT name, synonyms FROM agent '
                'WHERE nominal_target LIKE "%%%s%%" ' % target_name).fetchall()
        drug_names = [r[0] for r in res]
        return drug_names

    def find_mutation_effect(self, protein_name, amino_acid_change):
        match = re.match(r'([A-Z])([0-9]+)([A-Z])', amino_acid_change)
        if match is None:
            return None
        matches = match.groups()
        wt_residue = matches[0]
        pos = matches[1]
        sub_residue = matches[2]

        for stmt in self.sub_statements:
            if stmt.monomer.name == protein_name and\
                stmt.wt_residue == wt_residue and\
                stmt.pos == pos and\
                stmt.sub_residue == sub_residue:
                if stmt.rel == 'increases':
                    return 'activate'
                else:
                    return 'deactivate'
        return None
    
    def get_mutation_statistics(self, disease_name_filter, mutation_type):
        study_ids = cbio_client.get_cancer_studies(disease_name_filter)
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
            for g,a in zip(mutations['gene_symbol'], mutations['amino_acid_change']):
                mutation_effect = self.find_mutation_effect(g, a)
                if mutation_effect is None:
                    mutation_effect_key = 'other'
                else:
                    mutation_effect_key = mutation_effect
                try:
                    mutation_dict[g][0] += 1.0
                    mutation_dict[g][1][mutation_effect_key] += 1
                except KeyError:
                    effect_dict = {'activate': 0.0, 'deactivate': 0.0, 'other': 0.0}
                    effect_dict[mutation_effect_key] += 1.0
                    mutation_dict[g] = [1.0, effect_dict]
        # Normalize entries
        for k, v in mutation_dict.iteritems():
            mutation_dict[k][0] /= num_case
            effect_sum = numpy.sum(mutation_dict[k][1].values())
            mutation_dict[k][1]['activate'] /= effect_sum
            mutation_dict[k][1]['deactivate'] /= effect_sum
            mutation_dict[k][1]['other'] /= effect_sum

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
