import glob
import pickle
from indra.db import get_primary_db
from indra.db.util import make_stmts_from_db_list
from indra.assemblers.cx import CxAssembler

data_path = '/pmc/data/db_ndex'


def dump_statement_batch(stmts, fname):
    print('Dumping into %s' % fname)
    with open(fname, 'wb') as fh:
        pickle.dump(stmts, fh)


def load_statements():
    fnames = glob.glob(data_path + 'pa_stmts_*.pkl')
    all_stmts = []
    for fname in fnames:
        print('Loading %s' % fname)
        with open(fname, 'rb') as fh:
            stmts = pickle.load(fh)
            all_stmts += stmts
    return all_stmts


def assemble_cx(statements):
    cxa = CxAssembler(statements)
    model = cxa.make_model()
    cxa.save_model('model.cx')

if __name__ == '__main__':
    db = get_primary_db()
    res = db.filter_query(db.PAStatements).yield_per(20000)
    stmts = []
    for idx, r in enumerate(res):
        stmt = make_stmts_from_db_list([r])
        stmts.append(stmt[0])
        if idx > 0 and idx % 20000 == 0:
            dump_statement_batch(stmts, data_path + 'pa_stmts_%d.pkl' % idx)
            stmts = []
