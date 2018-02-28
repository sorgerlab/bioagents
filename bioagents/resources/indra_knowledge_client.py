import os
import requests

from indra.statements import stmts_from_json


INDRA_DB_API = os.environ['INDRA_DB_API']
INDRA_DB_API_KEY = os.environ['INDRA_DB_API_KEY']


class IndraKnowledgeQueryError(Exception):
    pass


def query_database(*args, **kwargs):
    query_str = '&'.join(['%s=%s' % (k, v) for k, v in kwargs.items()]
                         + list(args))
    resp = requests.get(INDRA_DB_API + '/statements/?%s' % query_str,
                        headers={'x-api-key': INDRA_DB_API_KEY})
    if resp.status_code != 200:
        raise IndraKnowledgeQueryError('Got bad status code %d: %s'
                                       % (resp.status_code, resp.data))
    return stmts_from_json(resp.json())