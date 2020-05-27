import os
from xml.etree import ElementTree as ET
from indra.ontology import IndraOntology


here = os.path.dirname(os.path.abspath(__file__))
ont_xml_path = os.path.join(here, 'trips-ont-dsl.xml')


class TripsOntology(IndraOntology):
    def __init__(self, xml_path=ont_xml_path):
        super().__init__()
        self.tree = ET.parse(xml_path)

    def initialize(self):
        concepts = self.tree.findall('concept')
        edges = []
        for concept in concepts:
            name = concept.attrib['name'].upper()
            if name == 'root':
                continue
            relations = concept.find("relation[@label='inherit']")
            # E.g., for the ONT:ROOT there is no relation
            if relations is None:
                continue
            related_names = [rr.strip().upper() for rr
                             in relations.text.strip().split('\n')]
            for related_name in related_names:
                edges.append((self.label('TRIPS', name),
                              self.label('TRIPS', related_name),
                              {'type': 'isa'}))
        self.add_edges_from(edges)


trips_ontology = TripsOntology()
trips_ontology.initialize()


def trips_isa(concept1, concept2):
    concept1 = normalize_entry(concept1)
    concept2 = normalize_entry(concept2)
    return trips_ontology.isa('TRIPS', concept1,
                              'TRIPS', concept2)


def normalize_entry(txt):
    txt = txt.upper()
    if not txt.startswith('ONT::'):
        txt = 'ONT::%s' % txt
    return txt