import suds
import re
import logging

logger = logging.getLogger('suds')
logger.setLevel(logging.ERROR)

chebi_wsdl = 'http://www.ebi.ac.uk/webservices/chebi/2.0/webservice?wsdl'
try:
    chebi_client = suds.client.Client(chebi_wsdl)
except Exception as e:
    logger.error('ChEBI web service is unavailable.')
    chebi_client = None

def get_id(name, max_results=1):
    # TODO: reimplement to get result from actual returned object
    # not based on string matching
    if chebi_client is None:
        return None
    res = chebi_client.service.getLiteEntity(name, 'CHEBI NAME',
                                             max_results, 'ALL')
    res_str = str(res)
    if res_str == '':
        return None
    match = re.search(r'"CHEBI:(.*)"', res_str)
    chebi_id = match.groups()[0]
    return chebi_id
