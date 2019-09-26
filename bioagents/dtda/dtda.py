# DTDA stands for disease-target-drug agent whose task is to
# search for targets known to be implicated in a
# certain disease and to look for drugs that are known
# to affect that target directly or indirectly
import json
import re
import os
import numpy
import logging
from itertools import groupby

from indra.sources.indra_db_rest import get_statements
from indra.databases import cbio_client, hgnc_client
from bioagents import BioagentException
from indra.statements import Agent, MutCondition, InvalidResidueError

logger = logging.getLogger('DTDA')

_resource_dir = os.path.dirname(os.path.realpath(__file__)) + '/../resources/'


class DrugNotFoundException(BioagentException):
    pass


class DiseaseNotFoundException(BioagentException):
    pass


class DatabaseTimeoutError(BioagentException):
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

        # These two dicts will cache results from the database, and act as
        # a record of which targets and drugs have been search, which is why
        # the dicts are kept separate. That way we know that if Selumetinib
        # shows up in the drug_targets keys, all the targets of Selumetinib
        # will be present, while although Selumetinib may be a value in
        # target_drugs drugs, not all targets that have Selumetinib as a drug
        # will be keys.
        self.target_drugs = {}
        self.drug_targets = {}

        # The following are sets of the drugs and targets that we come across
        self.all_drugs = []
        self.all_targets = []
        self.all_diseases = list(cbio_efo_map.keys())

        # Load data directly from tas
        self._get_tas_stmts_directly()
        return

    def is_nominal_drug_target(self, drug, target):
        """Return True if the drug targets the target, and False if not."""
        targets = self.find_drug_targets(drug)
        if not targets:
            raise DrugNotFoundException
        if target.name in targets:
            return True
        return False

    def _get_tas_stmts_directly(self):
        logger.debug('Loading TAS Statements directly into cache.')
        from indra.sources import tas
        tp = tas.process_csv()

        # Here we figure out which drugs only have weak affinities
        stmts_by_drug = groupby(sorted(tp.statements,
                                       key=lambda x: x.subj.name),
                                key=lambda x: x.subj.name)
        drug_classes = {}
        for _, stmts in stmts_by_drug:
            stmts = list(stmts)
            aff = {stmt.evidence[0].annotations['class_min'] for stmt in stmts}
            drug_classes[stmts[0].subj.name] = 'has_strong' \
                if 'Kd < 100nM' in aff else 'not_has_strong'

        drug_set = set()
        target_set = set()
        for stmt in tp.statements:
            # Skip Statements where the affinity is low if it otherwise also
            # has strong affinity targets
            if drug_classes[stmt.subj.name] == 'has_strong' and \
               stmt.evidence[0].annotations['class_min'] != 'Kd < 100nM':
                continue

            # Add the interactors to their respective sets
            drug_set.add(json.dumps(stmt.subj.to_json()))
            target_set.add(json.dumps(stmt.obj.to_json()))

            # First we make the target to drug mapping
            target_hgnc = stmt.obj.db_refs['HGNC']
            if target_hgnc:
                target_key = (target_hgnc, 'HGNC')
            else:
                target_key = stmt.obj.name
            drug_key = (stmt.subj.name, stmt.subj.db_refs.get('PUBCHEM'))
            if target_key not in self.target_drugs:
                self.target_drugs[target_key] = [drug_key]
            else:
                self.target_drugs[target_key].append(drug_key)

            # Then we make the drug to target mapping where targets
            # only need a name
            drug_keys = [(di, dn) for dn, di in stmt.subj.db_refs.items()]
            drug_keys += [(stmt.subj.name.lower(), 'TEXT'),
                          (stmt.subj.name.upper(), 'TEXT'),
                          (stmt.subj.name.capitalize(), 'TEXT'),
                          (stmt.subj.name, 'TEXT'),]
            for drug_key in drug_keys:
                if drug_key not in self.drug_targets:
                    self.drug_targets[drug_key] = set([stmt.obj.name])
                else:
                    self.drug_targets[drug_key].add(stmt.obj.name)
        logger.debug('Loaded TAS Statements directly into cache.')

        self.all_drugs = [json.loads(ag_json) for ag_json in drug_set]
        self.all_targets = [json.loads(ag_json) for ag_json in target_set]
        return

    def _get_tas_stmts(self, drug_term=None, target_term=None):
        timeout = 10
        drug = _convert_term(drug_term)
        target = _convert_term(target_term)
        processor = get_statements(subject=drug, object=target,
                                   stmt_type='Inhibition', timeout=timeout)
        if processor.is_working():
            msg = ("Database has failed to respond after %d seconds looking "
                   "up %s inhibits %s." % (timeout, drug, target))
            logger.error(msg)
            raise DatabaseTimeoutError(msg)
        return (s for s in processor.statements
                if any(ev.source_api == 'tas' for ev in s.evidence))

    def _extract_terms(self, agent):
        term_set = {(ref, ns) for ns, ref in agent.db_refs.items()}

        # Try without a hyphen.
        if '-' in agent.name:
            term_set.add((agent.name.replace('-', ''), 'TEXT'))

        # Try different capitalizations.
        transforms = ['capitalize', 'upper', 'lower']
        for opp in map(lambda nm: getattr(agent.name, nm), transforms):
            term_set.add((opp(), 'TEXT'))

        return term_set

    def find_target_drugs(self, target):
        """Return all the drugs that target a given target."""
        # These are proteins/genes so we just look at HGNC grounding
        if 'HGNC' not in target.db_refs:
            return {}
        target_term = (target.db_refs['HGNC'], 'HGNC')
        # Check if we already have the stashed result
        if target_term not in self.target_drugs:
            logger.debug('Looking up target term in DB: %s' % str(target_term))
            try:
                drugs = {(s.subj.name, s.subj.db_refs.get('PUBCHEM'))
                         for s in self._get_tas_stmts(target_term=target_term)}
                self.target_drugs[target_term] = drugs
            except DatabaseTimeoutError:
                # TODO: We should return a special message if the database
                # can't be reached for some reason. It might also be good to
                # stash the cache dicts as back-ups.
                # If there is an error we don't stash the results
                return {}
        else:
            logger.debug('Getting target term directly from cache: %s'
                         % str(target_term))
            drugs = self.target_drugs[target_term]
        return drugs

    def find_drug_targets(self, drug):
        """Return all the targets of a given drug."""
        # Build a list of different possible identifiers
        drug_terms = self._extract_terms(drug)

        # Search for relations involving those identifiers.
        all_targets = set()
        for term in drug_terms:
            if term not in self.drug_targets:
                logger.debug('Looking up drug term in DB: %s' % str(term))
                try:
                    tas_stmts = self._get_tas_stmts(term)
                except DatabaseTimeoutError:
                    continue
                targets = {s.obj.name for s in tas_stmts}
                self.drug_targets[term] = targets
            else:
                logger.debug('Getting drug term directly from cache: %s'
                             % str(term))
                targets = self.drug_targets[term]
            all_targets |= targets
        return all_targets

    def find_mutation_effect(self, agent):
        if not agent.mutations or len(agent.mutations) < 1:
            return None
        mut = agent.mutations[0]

        if agent.name not in self.sub_statements:
            logger.info("Looking up: %s" % agent.name)
            self.sub_statements[agent.name] \
                = get_statements(agents=[agent.db_refs['HGNC'] + '@HGNC'],
                                 stmt_type='ActiveForm', simple_response=True)

        for stmt in self.sub_statements[agent.name]:
            mutations = stmt.agent.mutations
            # Make sure the Agent has exactly one mutation
            if len(mutations) != 1:
                continue
            if mutations[0].equals(mut):
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
        logger.info("Found %d studies and a gene_list of %d elements."
                    % (len(study_ids), len(gene_list)))
        mut_patt = re.compile("([A-Z]+)(\d+)([A-Z]+)")
        for study_id in study_ids:
            num_case += cbio_client.get_num_sequenced(study_id)
            mutations = cbio_client.get_mutations(study_id, gene_list,
                                                  mutation_type)

            if not mutations['gene_symbol']:
                logger.info("Found no genes for %s." % study_id)
                continue

            # Create agents from the results of the search.
            agent_dict = {}
            for g, a in zip(mutations['gene_symbol'],
                            mutations['amino_acid_change']):
                m = mut_patt.match(a)
                if m is None:
                    logger.warning("Unrecognized residue: %s" % a)
                    continue
                res_from, pos, res_to = m.groups()
                try:
                    mut = MutCondition(pos, res_from, res_to)
                except InvalidResidueError:
                    logger.warning("Invalid residue: %s or %s."
                                   % (res_from, res_to))
                    continue
                ag = Agent(g, db_refs={'HGNC': hgnc_client.get_hgnc_id(g)},
                           mutations=[mut])
                if g not in agent_dict.keys():
                    agent_dict[g] = []
                agent_dict[g].append(ag)

            # Get the most mutated gene.
            top_gene = max(agent_dict.keys(),
                           key=lambda k: len(agent_dict[k]))
            logger.info("Found %d genes, with top hit %s for %s."
                        % (len(agent_dict.keys()), top_gene, study_id))

            if top_gene not in mutation_dict.keys():
                effect_dict = {'activate': 0, 'deactivate': 0,
                               'other': 0}
                mutation_dict[top_gene] = {'count': 0, 'effects': effect_dict,
                                           'total_effects': 0, 'agents': []}
            for agent in agent_dict[top_gene]:
                # Get the mutations effects for that gene.
                mutation_effect = self.find_mutation_effect(agent)
                if mutation_effect is None:
                    mutation_effect_key = 'other'
                else:
                    mutation_effect_key = mutation_effect
                mutation_dict[top_gene]['count'] += 1
                mutation_dict[top_gene]['effects'][mutation_effect_key] += 1
                mutation_dict[top_gene]['agents'].append(agent)

        # Calculate normalized entries
        for k, v in mutation_dict.items():
            mutation_dict[k]['fraction'] = v['count'] / num_case
            for eff in v['effects'].copy().keys():
                v['effects'][eff + '_percent'] = v['effects'][eff] / v['count']

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
        proteins_sorted = sorted(mutation_stats.keys(),
                                 key=lambda k: mutation_stats[k]['fraction'],
                                 reverse=True)
        mut_protein = proteins_sorted[0]
        mut_percent = int(mutation_stats[mut_protein]['fraction']*100.0)
        # TODO: return mutated residues
        # Doing even better, returning a list of agents.
        agents = mutation_stats[mut_protein]['agents']
        return mut_protein, mut_percent, agents

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


def get_disease(disease_ekb):
        term = disease_ekb.find('TERM')
        disease_type = term.find('type').text
        if disease_type.startswith('ONT::'):
            disease_type = disease_type[5:].lower()
        drum_term = term.find('drum-terms/drum-term')
        if drum_term is None:
            dbname = term.find('name').text
            dbid_dict = {}
        else:
            dbname = drum_term.attrib['name']
            dbid = drum_term.attrib['dbid']
            dbids = dbid.split('|')
            dbid_dict = {k: v for k, v in [d.split(':') for d in dbids]}
        disease = Disease(disease_type, dbname, dbid_dict)
        return disease


def _convert_term(term):
    if term is not None:
        return '%s@%s' % tuple(term)
    return
