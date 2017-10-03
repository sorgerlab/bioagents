import os
from indra.preassembler.hierarchy_manager import HierarchyManager

# Make a TRIPS ontology
_fname = os.path.join(os.path.dirname(__file__), 'trips_ontology.rdf')
trips_ontology = HierarchyManager(_fname, uri_as_name=False)
trips_ontology.relations_prefix = 'http://trips.ihmc.us/relations/'
trips_ontology.initialize()

def trips_isa(concept1, concept2):
    # Preprocess to make this more general
    concept1 = concept1.lower().replace('ont::', '')
    concept2 = concept2.lower().replace('ont::', '')
    isa = trips_ontology.isa('http://trips.ihmc.us/concepts/', concept1,
                             'http://trips.ihmc.us/concepts/', concept2)
    return isa
