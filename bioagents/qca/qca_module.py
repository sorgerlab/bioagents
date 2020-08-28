import os
import sys
import json
import logging
from bioagents import Bioagent, get_img_path
from kqml import KQMLList, KQMLString
from .qca import QCA
from indra.statements import stmts_from_json
from indra.assemblers.english import EnglishAssembler
from indra.sources.trips.processor import TripsProcessor


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('QCA')


class QCA_Module(Bioagent):
    '''
    The QCA module is a TRIPS module built around the QCA agent.
    Its role is to receive and decode messages and send responses from and
    to other agents in the system.
    '''
    name = 'QCA'
    tasks = ['FIND-QCA-PATH', 'HAS-QCA-PATH']

    def __init__(self, **kwargs):
        # For local testing use
        # qca_args = {'path_host': 'localhost',
        #            'network_uuid': '04020c47-4cfd-11e8-a4bf-0ac135e8bacf'}
        qca_args = {'path_host': '34.230.33.149',
                    'network_uuid': '50e3dff7-133e-11e6-a039-06603eb7f303'}
        # qca_args = {}
        # Instantiate a singleton QCA agent
        self.qca = QCA(**qca_args)
        # Call the constructor of Bioagent
        super(QCA_Module, self).__init__(**kwargs)

    def respond_find_qca_path(self, content):
        """Response content to find-qca-path request"""
        if self.qca.ndex is None:
            reply = self.make_failure('SERVICE_UNAVAILABLE')
            return reply

        source_arg = content.get('SOURCE')
        target_arg = content.get('TARGET')
        reltype_arg = content.get('RELTYPE')

        if not source_arg:
            raise ValueError("Source list is empty")
        if not target_arg:
            raise ValueError("Target list is empty")

        target = self.get_agent(target_arg)
        if target is None:
            reply = self.make_failure('NO_PATH_FOUND')
            # NOTE: use the one below if it's handled by NLG
            #reply = self.make_failure('TARGET_MISSING')
            return reply

        source = self.get_agent(source_arg)
        if source is None:
            reply = self.make_failure('NO_PATH_FOUND')
            # NOTE: use the one below if it's handled by NLG
            #reply = self.make_failure('SOURCE_MISSING')
            return reply

        if reltype_arg is None or len(reltype_arg) == 0:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        results_list = self.qca.find_causal_path([source.name], [target.name],
                                                 relation_types=relation_types)
        if not results_list:
            reply = self.make_failure('NO_PATH_FOUND')
            return reply

        def get_path_statements(results_list):
            stmts_list = []
            for res in results_list:
                # Edges of the first result
                edges = res[1::2]
                # INDRA JSON of the edges of the result
                try:
                    indra_edges = [fe[0]['__INDRA json'] for fe in edges]
                except Exception:
                    indra_edges = [fe[0]['INDRA json'] for fe in edges]
                # Make the JSONs dicts from strings
                indra_edges = [json.loads(e) for e in indra_edges]
                # Now fix the edges if needed due to INDRA Statement changes
                indra_edges = _fix_indra_edges(indra_edges)
                stmts_list.append(indra_edges)
            return stmts_list

        paths_list = get_path_statements(results_list)

        self.report_paths_graph(paths_list)

        # Take the first one to report
        indra_edges = paths_list[0]
        # Get the INDRA Statement objects
        indra_edge_stmts = stmts_from_json(indra_edges)
        # Assemble into English
        for stmt in indra_edge_stmts:
            txt = EnglishAssembler([stmt]).make_model()
            self.send_provenance_for_stmts(
                [stmt], "the path from %s to %s (%s)" % (source, target, txt))
        edges_cl_json = self.make_cljson(indra_edge_stmts)
        paths = KQMLList()
        paths.append(edges_cl_json)
        reply = KQMLList('SUCCESS')
        reply.set('paths', paths)

        return reply

    def report_paths_graph(self, paths_list):
        from indra.assemblers.graph import GraphAssembler
        from indra.util import flatten
        path_stmts = [stmts_from_json(l) for l in paths_list]
        all_stmts = flatten(path_stmts)
        ga = GraphAssembler(all_stmts)
        ga.make_model()
        resource = get_img_path('qca_paths.png')
        ga.save_pdf(resource)
        content = KQMLList('display-image')
        content.set('type', 'simulation')
        content.sets('path', resource)
        self.tell(content)

    def respond_has_qca_path(self, content):
        """Response content to find-qca-path request."""
        target_arg = content.get('TARGET')
        source_arg = content.get('SOURCE')
        reltype_arg = content.get('RELTYPE')

        if not source_arg:
            raise ValueError("Source list is empty")
        if not target_arg:
            raise ValueError("Target list is empty")

        target = self.get_agent(target_arg)
        source = self.get_agent(source_arg)

        if reltype_arg is None or len(reltype_arg) == 0:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        has_path = self.qca.has_path([source.name], [target.name])

        reply = KQMLList('SUCCESS')
        reply.set('haspath', 'TRUE' if has_path else 'FALSE')

        return reply

    def _get_term_name(self, term_str):
        tp = TripsProcessor(term_str)
        terms = tp.tree.findall('TERM')
        if not terms:
            return None
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        if agent is None:
            return None
        return agent.name


def _fix_indra_edges(stmt_json_list):
    """Temporary fixes to latest INDRA representation."""
    for stmt in stmt_json_list:
        if stmt.get('type') == 'RasGef':
            stmt['type'] = 'Gef'
        if stmt.get('type') == 'RasGap':
            stmt['type'] = 'Gap'
    return stmt_json_list


if __name__ == "__main__":
    QCA_Module(argv=sys.argv[1:])
