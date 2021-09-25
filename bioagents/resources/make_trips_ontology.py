import os
import sys
import xml.etree.ElementTree as ET
from rdflib import Graph, Namespace, Literal


trips_ns = Namespace('http://trips.ihmc.us/concepts/')
isa_rel = Namespace('http://trips.ihmc.us/relations/').term('isa')


def save_hierarchy(g, path):
    gs = g.serialize(format='nt')
    # For rdflib compatibility, handle both bytes and str
    if isinstance(gs, bytes):
        gs = gs.decode('utf-8')
    # Replace extra new lines in string and get rid of empty line at end
    g = gs.replace('\n\n', '\n').strip()
    # Split into rows and sort
    rows = gs.split('\n')
    rows.sort()
    gs = '\n'.join(rows)
    with open(path, 'w') as out_file:
        out_file.write(gs)


def make_hierarchy(tree):
    g = Graph()
    concepts = tree.findall('concept')
    for concept in concepts:
        name = concept.attrib['name'].replace('ont::', '')
        if name == 'root':
            continue
        term = trips_ns.term(name)
        relations = concept.find("relation[@label='inherit']")
        related_names = [rr.strip().replace('ont::', '') for rr
                        in relations.text.strip().split('\n')]
        for related_name in related_names:
            related_term = trips_ns.term(related_name)
            g.add((term, isa_rel, related_term))
    return g


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python make_trips_ontology.py /path/to/trips-ont-dsl.xml')
        sys.exit()
    fname = sys.argv[1]
    tree = ET.parse(fname)
    g = make_hierarchy(tree)
    save_hierarchy(g, 'trips_ontology.rdf')
