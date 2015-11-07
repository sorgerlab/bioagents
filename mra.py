# MRA stands for mechanistic reasoning agent. 
# Its task is to use INDRA to construct mechanistic models of 
# biochemical systems from natural language, publications
# and databases.

from indra import pysb_assembler
from indra.biopax import biopax_api
from indra.trips import trips_api

class MRA:
    def __init__(self):
        pass

    def find_mechanism(self, source, target, force_contains):
        bp = biopax_api.process_pc_pathsfromto(source, target, neighbor_limit=5)
        return bp

    def build_model(self, model_txt):
        pa = indra.PysbAssembler()
        tp = trips_api.process_text(model_txt)
        pa.add_statements(tp.statements)
        model = pa.make_model()
        return model


if __name__ == '__main__':
    mra = MRA()
    model = mra.build_model('EGF stimulation leads to the activity of HRAS')
     
    
