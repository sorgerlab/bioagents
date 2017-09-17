import os
import json
from kqml import KQMLString
from indra.statements import stmts_to_json
from indra.sources import trips


def ekb_from_text(text):
    ekb_xml = read_or_load(text)
    return ekb_xml


def ekb_kstring_from_text(text):
    ekb_xml = ekb_from_text(text)
    ks = KQMLString(ekb_xml)
    return ks


def stmts_json_from_text(text):
    ekb_xml = read_or_load(text)
    tp = trips.process_xml(ekb_xml)
    stmts_json = stmts_to_json(tp.statements)
    return stmts_json


def stmts_kstring_from_text(text):
    stmts_json = stmts_json_from_text(text)
    ks = KQMLString(json.dumps(stmts_json))
    return ks


cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'ekb_cache.json')


def _load_ekb_cache():
    with open(cache_file, 'r') as fh:
        ekb_cache = json.load(fh)
    return ekb_cache
ekb_cache = _load_ekb_cache()


def read_or_load(text, force_rewrite=False):
    if force_rewrite or text not in ekb_cache:
        html = trips.trips_client.send_query(text)
        ekb_xml = trips.trips_client.get_xml(html)
        ekb_cache[text] = ekb_xml
        with open(cache_file, 'w') as fh:
            json.dump(ekb_cache, fh, indent=1)
    else:
        ekb_xml = ekb_cache[text]
    return ekb_xml
