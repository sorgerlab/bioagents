# DTDA stands for disease-target-drug agent whose task is to
# search for targets known to be implicated in a
# certain disease and to look for drugs that are known
# to affect that target directly or indirectly

import re
import os
import numpy
import pickle
import logging
import sqlite3
import operator

from indra.sources.indra_db_rest import get_statements
from indra.statements import ActiveForm
from indra.databases import cbio_client
from bioagents import BioagentException

logger = logging.getLogger('DTDA')

_resource_dir = os.path.dirname(os.path.realpath(__file__)) + '/../resources/'


class DrugNotFoundException(BioagentException):
    pass


class DiseaseNotFoundException(BioagentException):
    pass


def _make_cbio_efo_map():
    lines = open(_resource_dir + 'cbio_efo_map.tsv', 'rt').readlines()
    cbio_efo_map = {}
    for lin in lines:
        cbio_id, efo_id = lin.strip().split('\t')
        try:
            cbio_efo_map[efo_id].append(cbio_id)
        except KeyError:
            cbio_efo_map[efo_id] = [cbio_id]
    return cbio_efo_map


cbio_efo_map = _make_cbio_efo_map()


class DTDA(object):
    def __init__(self):
        # Initialize cache of substitution statements, which will populate
        # on-the-fly from the database.
        self.sub_statements = {}
        self.target_drugs = {}
        self.drug_targets = {}
        return

    def is_nominal_drug_target(self, drug_names, target_name):
        """Return True if the drug targets the target, and False if not."""
        no_result = True
        if self.drug_db is not None:
            for drug_name in drug_names:
                res = self.drug_db.execute('SELECT nominal_target FROM agent '
                                           'WHERE (synonyms LIKE "%%%s%%" '
                                           'OR name LIKE "%%%s%%")' %
                                           (drug_name, drug_name)).fetchall()
                if not res:
                    continue
                no_result = False
                for r in res:
                    if r[0].upper() == target_name.upper():
                        return True
        if no_result:
            raise DrugNotFoundException
        return False

    def _get_tas_stmts(self, **kwargs):
        return (s for s in get_statements(stmt_type='Inhibition', **kwargs)
                if any(ev.source_api == 'tas' for ev in s.evidence))

    def find_target_drugs(self, target_name):
        """Return all the drugs that nominally target the target."""
        if target_name not in self.target_drugs.keys():
            drugs = {(s.subj.name, s.subj.db_refs.get('PUBCHEM'))
                     for s in self._get_tas_stmts(object=target_name)}
            self.target_drugs[target_name] = drugs
        else:
            drugs = self.target_drugs[target_name]
        return map(list, zip(*drugs))

    def find_drug_targets(self, drug_name):
        """Return all the drugs that nominally target the target."""
        if drug_name not in self.drug_targets.keys():
            targets = {s.obj.name for s in self._get_tas_stmts(drug_name)}
            self.drug_targets[drug_name] = targets
        else:
            targets = self.drug_targets[drug_name]
        return targets

    def find_mutation_effect(self, protein_name, amino_acid_change):
        match = re.match(r'([A-Z])([0-9]+)([A-Z])', amino_acid_change)
        if match is None:
            return None
        matches = match.groups()
        wt_residue = matches[0]
        pos = matches[1]
        sub_residue = matches[2]

        if protein_name not in self.sub_statements.keys():
            self.sub_statements[protein_name] \
                = get_statements(agents=[protein_name], stmt_type='ActiveForm')

        for stmt in self.sub_statements[protein_name]:
            mutations = stmt.agent.mutations
            # Make sure the Agent has exactly one mutation
            if len(mutations) != 1:
                continue
            if mutations[0].residue_from == wt_residue and\
                mutations[0].position == pos and\
                mutations[0].residue_to == sub_residue:
                    if stmt.is_active:
                        return 'activate'
                    else:
                        return 'deactivate'
        return None

    @staticmethod
    def _get_studies_from_disease_name(disease_name):
        study_prefixes = cbio_efo_map.get(disease_name)
        if study_prefixes is None:
            return None
        study_ids = []
        for sp in study_prefixes:
            study_ids += cbio_client.get_cancer_studies(sp)
        return list(set(study_ids))

    def get_mutation_statistics(self, disease_name, mutation_type):
        study_ids = self._get_studies_from_disease_name(disease_name)
        if not study_ids:
            raise DiseaseNotFoundException
        gene_list = self._get_gene_list()
        mutation_dict = {}
        num_case = 0
        for study_id in study_ids:
            num_case += cbio_client.get_num_sequenced(study_id)
            mutations = cbio_client.get_mutations(study_id, gene_list,
                                                  mutation_type)
            for g, a in zip(mutations['gene_symbol'],
                            mutations['amino_acid_change']):
                mutation_effect = self.find_mutation_effect(g, a)
                if mutation_effect is None:
                    mutation_effect_key = 'other'
                else:
                    mutation_effect_key = mutation_effect
                try:
                    mutation_dict[g][0] += 1.0
                    mutation_dict[g][1][mutation_effect_key] += 1
                except KeyError:
                    effect_dict = {'activate': 0.0, 'deactivate': 0.0,
                                   'other': 0.0}
                    effect_dict[mutation_effect_key] += 1.0
                    mutation_dict[g] = [1.0, effect_dict]
        # Normalize entries
        for k, v in mutation_dict.items():
            mutation_dict[k][0] /= num_case
            effect_sum = numpy.sum(list(v[1].values()))
            mutation_dict[k][1]['activate'] /= effect_sum
            mutation_dict[k][1]['deactivate'] /= effect_sum
            mutation_dict[k][1]['other'] /= effect_sum

        return mutation_dict

    def get_top_mutation(self, disease_name):
        # First, look for possible disease targets
        try:
            mutation_stats = self.get_mutation_statistics(disease_name,
                                                          'missense')
        except DiseaseNotFoundException as e:
            logger.exception(e)
            raise DiseaseNotFoundException
        if mutation_stats is None:
            logger.error('No mutation stats')
            return None

        # Return the top mutation as a possible target
        mutations_sorted = sorted(mutation_stats.items(),
                                  key=lambda x: x[1][0],
                                  reverse=True)
        top_mutation = mutations_sorted[0]
        mut_protein = top_mutation[0]
        mut_percent = int(top_mutation[1][0]*100.0)
        # TODO: return mutated residues
        # mut_residues =
        return mut_protein, mut_percent

    def _get_gene_list(self):
        gene_list = []
        for one_list in self.gene_lists.values():
            gene_list += one_list
        return gene_list

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


class Disease(object):
    def __init__(self, disease_type, name, db_refs):
        self.disease_type = disease_type
        self.name = name
        self.db_refs = db_refs

    def __repr__(self):
        return 'Disease(%s, %s, %s)' % \
            (self.disease_type, self.name, self.db_refs)

    def __str__(self):
        return self.__repr__()
