import json
from kqml import KQMLString
from indra.statements import stmts_to_json
from indra.sources import trips


def ekb_from_text(text):
    html = trips.trips_client.send_query(text)
    ekb_xml = trips.trips_client.get_xml(html)
    return ekb_xml


def ekb_kstring_from_text(text):
    ekb_xml = ekb_from_text(text)
    ks = KQMLString(ekb_xml)
    return ks


def stmts_json_from_text(text):
    tp = trips.process_text(text)
    stmts_json = stmts_to_json(tp.statements)
    return stmts_json


def stmts_kstring_from_text(text):
    stmts_json = stmts_json_from_text(text)
    ks = KQMLString(json.dumps(stmts_json))
    return ks
