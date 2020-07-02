import os
import json
import logging
import requests
from collections import defaultdict


logger = logging.getLogger(__name__)

base_url = 'https://www.cbioportal.org/api'

resources_dir = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'resources')

patient_list_cache = os.path.join(resources_dir, 'cbio_patients.json')


def get_patient_list():
    if os.path.exists(patient_list_cache):
        logger.info('Loading patient list from cache at %s' %
                    patient_list_cache)
        with open(patient_list_cache, 'r') as fh:
            patient_list = json.load(fh)
    else:
        logger.info('Querying patient list from cBioPortal')
        url = base_url + '/patients'
        res = requests.get(url)
        patient_list = res.json()

        with open(patient_list_cache, 'w') as fh:
            json.dump(patient_list, fh, indent=1)

    patients_by_id = defaultdict(list)
    patients_by_study = defaultdict(list)
    for patient in patient_list:
        patients_by_id[patient['patientId']].append(patient)
        patients_by_study[patient['studyId']].append(patient)
    return dict(patients_by_id), dict(patients_by_study)


def get_patient_clinical_info(patient_id, study_id):
    url = base_url + '/studies/%s/patients/%s/clinical-data' % \
        (study_id, patient_id)
    res = requests.get(url)
    info = {entry['clinicalAttributeId']: entry['value']
            for entry in res.json()}
    return info


def get_molecular_profiles(study_id):
    url = base_url + '/studies/%s/molecular-profiles' % study_id
    res = requests.get(url)
    return res.json()


def get_mutations(molecular_profile_id, sample_id):
    url = base_url + '/molecular-profiles/%s/mutations/fetch' % \
        molecular_profile_id
    res = requests.post(url, json={'sampleIds': [sample_id]})
    return res.json()


def get_samples(patient_id, study_id):
    url = base_url + '/studies/%s/patients/%s/samples' % \
        (study_id, patient_id)
    res = requests.get(url)
    samples = res.json()
    return samples


def get_sample_clinical_info(study_id, sample_id):
    url = base_url + '/studies/%s/samples/%s/clinical-data' % \
          (study_id, sample_id)
    res = requests.get(url)
    info = {entry['clinicalAttributeId']: entry['value']
            for entry in res.json()}
    return info


def get_study_clinical_attributes(study_id):
    url = base_url + '/studies/%s/clinical-attributes' % study_id
    res = requests.get(url)
    attributes = res.json()
    # of interest: displayName and clinicalAttributeId
    return attributes


class Sample:
    def __init__(self, sample_id, study_id):
        self.sample_id = sample_id
        self.study_id = study_id
        self.clinical_info = get_sample_clinical_info(self.study_id,
                                                      self.sample_id)


class Patient:
    def __init__(self, patient_id, study_id=None):
        self.patient_id = patient_id
        if study_id is None:
            studies = patients_by_id[patient_id]
            self.study_id = studies[0]['studyId']
        else:
            self.study_id = study_id
        self.clinical_info = get_patient_clinical_info(self.patient_id,
                                                       self.study_id)
        samples = get_samples(self.patient_id, self.study_id)
        for sample in samples:
            if sample['sampleType'] == 'Primary Solid Tumor':
                self.sample = Sample(sample['sampleId'], self.study_id)

        assert self.sample

        mol_profiles = get_molecular_profiles(self.study_id)
        self.molecular_profiles = {}
        for entry in mol_profiles:
            self.molecular_profiles[entry['molecularAlterationType']] = entry

        if 'MUTATION_EXTENDED' in self.molecular_profiles:
            mutation_profile_id = \
                self.molecular_profiles['MUTATION_EXTENDED'][
                    'molecularProfileId']
            self.mutations = \
                get_mutations(mutation_profile_id,
                              self.sample.sample_id)

        '''
        if 'COPY_NUMBER_ALTERATION' in self.molecular_profiles:
            cna_profile_id = \
                self.molecular_profiles['COPY_NUMBER_ALTERATION'][
                    'molecularProfileId']
            self.cna = \
        '''


patients_by_id, patients_by_study = get_patient_list()
