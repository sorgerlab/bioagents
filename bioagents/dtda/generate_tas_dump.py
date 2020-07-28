import os
import pickle
from collections import defaultdict
from indra.sources import tas
from indra.databases import drugbank_client


def normalize_drug(drug):
    flags = score_drug(drug)
    if 'long_name' in flags:
        if 'DRUGBANK' in drug.db_refs:
            db_name = \
                drugbank_client.get_drugbank_name(drug.db_refs['DRUGBANK'])
            if db_name:
                drug.name = db_name


def score_drug(drug):
    flags = set()
    if any(char in drug.name for char in {'(', '[', '{', ','}):
        flags.add('has_special_char')
    if 'CHEBI' not in drug.db_refs and 'CHEMBL' in drug.db_refs:
        flags.add('chembl_not_chebi')
    if len(drug.name) > 20:
        flags.add('long_name')
    if ' ' in drug.name:
        flags.add('has_space')
    return flags


def choose_best_stmt(stmt_group):
    for stmt in stmt_group:
        normalize_drug(stmt.subj)
    stmts = sorted(stmt_group,
                   key=lambda x:
                    (len(score_drug(x.subj)),
                     len(x.subj.name)))
    if len(stmt_group) > 1:
        print('Choosing: %s (%s) from' %
              (stmts[0].subj, score_drug(stmts[0].subj)))
        for stmt in stmts:
            print(stmt.subj, score_drug(stmt.subj))
        print()
    return stmts[0]


if __name__ == '__main__':
    tp = tas.process_from_web(affinity_class_limit=2, named_only=True,
                              standardized_only=False)
    grouped = defaultdict(list)
    for stmt in tp.statements:
        grouped[(stmt.subj.db_refs['LSPCI'], stmt.obj.name)].append(stmt)

    opt_stmts = []
    for (lspci, obj_name), stmts in grouped.items():
        if obj_name == 'PTPN11':
            breakpoint()
        opt_stmt = choose_best_stmt(stmts)
        opt_stmts.append(opt_stmt)

    fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir, 'resources', 'tas_stmts_filtered.pkl')
    with open(fname, 'wb') as fh:
        pickle.dump(opt_stmts, fh)
