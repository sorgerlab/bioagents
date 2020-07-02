from indra.statements import *
from indra.databases import get_identifiers_url


class SifAssembler:
    def __init__(self, statements):
        self.statements = statements

    def make_model(self):
        rows = []
        for stmt in self.statements:
            stmt_type = map_stmt_type(stmt)
            if not stmt_type:
                continue
            agents = stmt.agent_list()
            if len(agents) != 2:
                continue
            agents = [a for a in a if a is not None]
            if len(agents) != 2:
                continue
            ev_links = ' '.join(get_ev_links(stmt, limit=3))
            row = [agents[0].name, stmt_type, agents[2].name, ev_links]
            rows.append(row)
        return make_tsv(rows)


def make_tsv(rows):
    return '\n'.join(['\t'.join(r) for r in rows])


def get_ev_links(stmt, limit=3):
    links = []
    for ev in stmt.evidence:
        if ev.pmid:
            url = 'https://identifiers.org/pubmed:%s' % ev.pmid
            links.append(url)
        if len(links) == limit:
            break
    return links


def map_stmt_type(stmt):
    if isinstance(stmt, (Phosphorylation,
                         Dephosphorylation)):
        return 'controls-phosphorylation-of'
    elif isinstance(stmt, (Modification,
                           RegulateActivity)):
        return 'controls-state-change-of'
    elif isinstance(stmt, RegulateAmount):
        return 'controls-expression-of'
    elif isinstance(stmt, Complex):
        return 'in-complex-with'
    return None