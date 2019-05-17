import os
import json
from collections import OrderedDict
import xml.etree.ElementTree as ET
from kqml import KQMLString, KQMLPerformative
from indra.sources import trips
from indra.statements import stmts_to_json, Agent
from bioagents import Bioagent


def ekb_from_text(text):
    """Return an EKB XML from the cache or by TRIPS reading from text."""
    ekb_xml = read_or_load(text)
    return ekb_xml


def ekb_kstring_from_text(text):
    """Return a KQML string representation of an EKB from text."""
    ekb_xml = ekb_from_text(text)
    ks = KQMLString(ekb_xml)
    return ks


def agent_from_text(text):
    """Return a single INDRA Agent from text."""
    ekb_xml = ekb_from_text(text)
    tp = trips.process_xml(ekb_xml)
    agents = tp.get_agents()
    for agent in agents:
        if agent.bound_conditions:
            return agent
    return agents[0]


def agent_clj_from_text(text):
    """Return an INDRA Agent CL-JSON from text."""
    agent = agent_from_text(text)
    clj = Bioagent.make_cljson(agent)
    return clj


def stmts_from_text(text):
    """Return a list of INDRA Statements from text."""
    ekb_xml = read_or_load(text)
    tp = trips.process_xml(ekb_xml)
    return tp.statements


def stmts_json_from_text(text):
    """Return an INDRA Statements JSON from text."""
    stmts_json = stmts_to_json(stmts_from_text(text))
    return stmts_json


def stmts_clj_from_text(text):
    """Return a CL-JSON representation of INDRA Statements from text."""
    stmts = stmts_from_text(text)
    stmts_clj = Bioagent.make_cljson(stmts)
    return stmts_clj


def stmts_kstring_from_text(text):
    """Return a KQML string representation of INDRA Statements JSON from
    text."""
    stmts_json = stmts_json_from_text(text)
    ks = KQMLString(json.dumps(stmts_json))
    return ks


def get_request(content):
    """Make a request KQML performative wrapping some KQML content."""
    msg = KQMLPerformative('REQUEST')
    msg.set('content', content)
    msg.set('reply-with', 'IO-1')
    return msg


cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'ekb_cache.json')


def _load_ekb_cache():
    with open(cache_file, 'r') as fh:
        ekb_cache = json.load(fh)
    return ekb_cache
ekb_cache = _load_ekb_cache()


def read_or_load(text, force_rewrite=False):
    if force_rewrite or text not in ekb_cache:
        html = trips.client.send_query(text, service_endpoint='drum-dev')
        ekb_xml = trips.client.get_xml(html)
        ekb_cache[text] = ekb_xml
        ekb_cache_items = sorted(ekb_cache.items(), key=lambda x: x[0])
        ekb_cache_ordered = OrderedDict(ekb_cache_items)
        with open(cache_file, 'w') as fh:
            json.dump(ekb_cache_ordered, fh, indent=1)
    else:
        ekb_xml = ekb_cache[text]
    return ekb_xml
