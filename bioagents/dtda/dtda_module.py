import sys
import logging
import xml.etree.ElementTree as ET
from indra.sources.trips.processor import TripsProcessor
from kqml import KQMLList
from .dtda import DTDA, Disease, \
                  DrugNotFoundException, DiseaseNotFoundException
from bioagents import Bioagent
from bioagents.resources.trips_ont_manager import trips_isa


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('DTDA')


class DTDA_Module(Bioagent):
    """The DTDA module is a TRIPS module built around the DTDA agent.
    Its role is to receive and decode messages and send responses from and
    to other agents in the system."""
    name = "DTDA"
    tasks = ['IS-DRUG-TARGET', 'FIND-TARGET-DRUG', 'FIND-DRUG-TARGETS',
             'FIND-DISEASE-TARGETS', 'FIND-TREATMENT']

    def __init__(self, **kwargs):
        # Instantiate a singleton DTDA agent
        self.dtda = DTDA()
        super(DTDA_Module, self).__init__(**kwargs)

    def respond_is_drug_target(self, content):
        """Response content to is-drug-target request."""
        try:
            drug_arg = content.gets('drug')
        except Exception:
            return self.make_failure('INVALID_DRUG')
        try:
            drug = self._get_agent(drug_arg)
        except Exception:
            return self.make_failure('DRUG_NOT_FOUND')
        try:
            target_arg = content.gets('target')
            target = self._get_agent(target_arg)
            target_name = target.name
        except Exception:
            return self.make_failure('INVALID_TARGET')

        try:
            is_target = self.dtda.is_nominal_drug_target(drug, target_name)
        except DrugNotFoundException:
            return self.make_failure('DRUG_NOT_FOUND')
        reply = KQMLList('SUCCESS')
        reply.set('is-target', 'TRUE' if is_target else 'FALSE')
        return reply

    def respond_find_target_drug(self, content):
        """Response content to find-target-drug request."""
        try:
            target_arg = content.gets('target')
            target = self._get_agent(target_arg)
            target_name = target.name
        except Exception:
            return self.make_failure('INVALID_TARGET')
        drug_names, pubchem_ids = self.dtda.find_target_drugs(target_name)
        reply = KQMLList('SUCCESS')
        drugs = KQMLList()
        for dn, pci in zip(drug_names, pubchem_ids):
            drug = KQMLList()
            drug.set('name', dn.replace(' ', '-'))
            if pci:
                drug.set('pubchem_id', pci)
            drugs.append(drug)
        reply.set('drugs', drugs)
        return reply

    def respond_find_drug_targets(self, content):
        """Response content to find-drug-target request."""
        try:
            drug_arg = content.gets('drug')
            drug = self._get_agent(drug_arg)
        except Exception as e:
            return self.make_failure('INVALID_DRUG')
        logger.info('DTDA looking for targets of %s' % drug.name)
        drug_targets = self.dtda.find_drug_targets(drug)
        all_targets = sorted(list(set(drug_targets)))

        reply = KQMLList('SUCCESS')
        targets = KQMLList()
        for target_name in all_targets:
            target = KQMLList()
            target.set('name', target_name)
            targets.append(target)
        reply.set('targets', targets)
        return reply

    def respond_find_disease_targets(self, content):
        """Response content to find-disease-targets request."""
        try:
            disease_arg = content.gets('disease')
            disease = self.get_disease(disease_arg)
        except Exception as e:
            logger.error(e)
            reply = self.make_failure('INVALID_DISEASE')
            return reply

        if not trips_isa(disease.disease_type, 'ont::cancer'):
            reply = self.make_failure('DISEASE_NOT_FOUND')
            return reply

        logger.debug('Disease: %s' % disease.name)

        try:
            mut_protein, mut_percent = \
                self.dtda.get_top_mutation(disease.name)
        except DiseaseNotFoundException:
            reply = self.make_failure('DISEASE_NOT_FOUND')
            return reply

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from DTDA
        reply = KQMLList('SUCCESS')
        protein = KQMLList()
        protein.set('name', mut_protein)
        protein.set('hgnc', mut_protein)
        reply.set('protein', protein)
        reply.set('prevalence', '%.2f' % (mut_percent/100.0))
        reply.set('functional-effect', 'ACTIVE')
        return reply

    def respond_find_treatment(self, content):
        """Response content to find-treatment request."""
        try:
            disease_arg = content.gets('disease')
            disease = self.get_disease(disease_arg)
        except Exception as e:
            logger.error(e)
            reply = self.make_failure('INVALID_DISEASE')
            return reply


        logger.info('Disease type: %s' % disease.disease_type)

        if not trips_isa(disease.disease_type, 'ont::cancer'):
            logger.info('Disease is not a type of cancer.')
            reply = self.make_failure('DISEASE_NOT_FOUND')
            return reply

        logger.debug('Disease: %s' % disease.name)

        try:
            mut_protein, mut_percent = \
                self.dtda.get_top_mutation(disease.name)
        except DiseaseNotFoundException:
            reply = self.make_failure('DISEASE_NOT_FOUND')
            return reply

        reply = KQMLList()

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from DTDA
        reply1 = KQMLList('SUCCESS')
        protein = KQMLList()
        protein.set('name', mut_protein)
        protein.set('hgnc', mut_protein)
        reply1.set('protein', protein)
        reply1.set('prevalence', '%.2f' % (mut_percent/100.0))
        reply1.set('functional-effect', 'ACTIVE')
        reply.append(reply1)

        reply2 = KQMLList('SUCCESS')
        drug_names, pubchem_ids = self.dtda.find_target_drugs(mut_protein)
        drugs = KQMLList()
        for dn, pci in zip(drug_names, pubchem_ids):
            drug = KQMLList()
            drug.sets('name', dn.replace(' ', '-'))
            if pci:
                drug.set('pubchem_id', pci)
            drugs.append(drug)
        reply2.set('drugs', drugs)

        reply.append(reply2)
        return reply

    @staticmethod
    def _get_agent(agent_ekb):
        tp = TripsProcessor(agent_ekb)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent

    @staticmethod
    def get_disease(disease_str):
        term = ET.fromstring(disease_str).find('TERM')
        disease_type = term.find('type').text
        if disease_type.startswith('ONT::'):
            disease_type = disease_type[5:].lower()
        drum_term = term.find('drum-terms/drum-term')
        if drum_term is None:
            dbname = term.find('name').text
            dbid_dict = {}
        else:
            dbname = drum_term.attrib['name']
            dbid = term.attrib['dbid']
            dbids = dbid.split('|')
            dbid_dict = {k: v for k, v in [d.split(':') for d in dbids]}
        disease = Disease(disease_type, dbname, dbid_dict)
        return disease


if __name__ == "__main__":
    DTDA_Module(argv=sys.argv[1:])
