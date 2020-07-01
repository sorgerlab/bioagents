import os
import json
import logging
import requests
from collections import defaultdict


logger = logging.getLogger(__name__)

base_url = 'https://www.cbioportal.org/api'

resources_dir = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), os.pardir, 'resources')

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


patients_by_id, patients_by_study = get_patient_list()
