# QCA stands for qualitative causal agent whose task is to
# identify causal paths within

import json
import logging
import requests
import functools
import ndex2.client as nc
from enum import Enum
from bioagents import BioagentException


logger = logging.getLogger('QCA')


class PathNotFoundException(BioagentException):
    def __init__(self, *args, **kwargs):
            Exception.__init__(self, *args, **kwargs)


class QCA(object):
    def __init__(self, path_host=None, network_uuid=None):
        logger.debug('Starting QCA')

        if not path_host:
            path_host = '34.230.33.149'

        if not network_uuid:
            network_uuid = '50e3dff7-133e-11e6-a039-06603eb7f303'

        logger.info('Using host %s and network %s' % (path_host, network_uuid))

        self.host = "http://www.ndexbio.org"

        self.results_directory = "qca_results"

        self.directed_path_query_url = \
            ('http://%s:5603/directedpath/query' % path_host)

        self.context_expression_query_url = \
            'http://general.bigmech.ndexbio.org:8081' + \
            '/context/expression/cell_line'

        self.context_mutation_query_url = \
            'http://general.bigmech.ndexbio.org:8081/' + \
            'context/mutation/cell_line'

        # dict of reference network descriptors by network name
        self.reference_networks = [
            #{
            #    "id": "84f321c6-dade-11e6-86b1-0ac135e8bacf",
            #    "name": "prior",
            #    "type": "canonical",
            #    "server": "public.ndexbio.org"
            #}
            {
                # Large network from preassembled DB
                # "id": "04020c47-4cfd-11e8-a4bf-0ac135e8bacf",
                # The RAS Machine network
                #"id": "50e3dff7-133e-11e6-a039-06603eb7f303",
                #"id": "d68677b8-173d-11e7-b39e-0ac135e8bacf",
                #"id": "89274295-1730-11e7-b39e-0ac135e8bacf",
                'id': network_uuid,
                "name": "Ras Machine",
                "type": "canonical",
                "server": "public.ndexbio.org"
            }
        ]

        # --------------------------
        # Schemas

        self.query_result_schema = {
            "network_description": {},
            "forward_paths": [],
            "reverse_paths": [],
            "forward_mutation_paths": [],
            "reverse_mutation_paths": []
        }

        self.reference_network_schema = {
            "id": "",
            "name": "",
            "type": "canonical"
        }

        self.query_schema = {
            "source_names": [],
            "target_names": [],
            "cell_line": ""
        }

        # --------------------------
        #  Cell Lines

        self.cell_lines = []

        # --------------------------
        #  Queries

        # list of query dicts
        self.queries = []

        try:
            self.ndex = nc.Ndex2(host=self.host)
        except Exception as e:
            logger.error('QCA could not connect to %s' % self.host)
            logger.error(e)
            self.ndex = None

    def find_causal_path(self, source_names, target_names,
                         exit_on_found_path=False, relation_types=None):
        '''
        Uses the source and target parameters to search for paths within
        predetermined directed networks.
        :param source_names: Source nodes
        :type source_names: Array of strings
        :param target_names: Target nodes
        :type target_names: Array of strings
        :param exit_on_found_path: Used for has_path()
        :type exit_on_found_path: Boolean
        :param relation_types: Edge types
        :type relation_types: Array of strings
        :return: Edge paths
        :rtype: Array of tuples
        '''
        results_list = []

        #==========================================
        # Find paths in all available networks
        #==========================================
        for network in self.reference_networks:
            pr = self.get_directed_paths_by_names(source_names, target_names,
                                                  network.get("id"),
                                                  network.get("server"),
                                                  relation_types=relation_types,
                                                  max_number_of_paths=50)
            prc = pr.content
            #==========================================
            # Process the data from this network
            #==========================================
            if prc is not None and len(prc.strip()) > 0:
                try:
                    # Dump the QCA result for debugging purposes
                    with open('qca_result.json', 'w') as fh:
                        json.dump(json.loads(prc.decode()), fh, indent=2)
                    result_json = json.loads(prc.decode())
                    if result_json.get('data') is not None and \
                       result_json.get("data").get("forward_english") is not None:
                        f_e = result_json.get("data").get("forward_english")

                        results_list += [f_e_i for f_e_i in f_e if len(f_e) > 0]
                        #============================================
                        # Return right away if the exit flag is set
                        #============================================
                        if len(results_list) > 0 and exit_on_found_path:
                            return results_list
                except ValueError as ve:
                    print(ve)
                    print("value is not json.  html 500?")

        path_scoring = PathScoring()

        results_list_sorted = sorted(
            results_list,
            key=functools.cmp_to_key(lambda x, y:
                                     path_scoring.cross_country_scoring(x, y))
            )

        return results_list_sorted

    def has_path(self, source_names, target_names):
        '''
        determine if there is a path between nodes within predetermined
        directed networks
        :param source_names: Source nodes
        :type source_names: Array of strings
        :param target_names: Target nodes
        :type target_names: Array of strings
        :return: Path exists
        :rtype: Boolean
        '''
        found_path = self.find_causal_path(source_names, target_names,
                                           exit_on_found_path=True)
        return len(found_path) > 0

    def get_directed_paths_by_names(self, source_names, target_names, uuid,
                                    server, max_number_of_paths=5,
                                    relation_types=None):
        #====================
        # Assemble REST url
        #====================
        target = ",".join(target_names)
        source = ",".join(source_names)
        pathnum = str(max_number_of_paths)
        url = self.directed_path_query_url + '?source=' + source + \
            '&target=' + target + '&pathnum=' + pathnum + \
            '&uuid=' + uuid + '&server=' + server
        if relation_types is not None:
            rts = " ".join(relation_types)
            url += '&relationtypes=' + rts

        r = requests.post(url)
        return r

    def get_path_node_names(self, query_result):
        return None

    def get_expression_context(self, node_name_list, cell_line_list):
        query_string = " ".join(node_name_list)
        params = json.dumps({query_string: cell_line_list})
        r = requests.post(self.context_expression_query_url, json=params)
        return r

    def get_mutation_context(self, node_name_list, cell_line_list):
        query_string = " ".join(node_name_list)
        params = json.dumps({query_string: cell_line_list})
        r = requests.post(self.context_mutation_query_url, json=params)
        return r

    def save_query_results(self, query, query_results):
        path = self.results_directory + "/" + query.get("name")
        outfile = open(path, 'wt')
        json.dump(query_results, outfile, indent=4)
        outfile.close()

    def get_mutation_paths(self, query_result, mutated_nodes,
                           reference_network):
        return None

    def create_merged_network(self, query_result):
        return None

    def run_query(self, query):
        query_results = {}

        for network_descriptor in self.reference_networks:
            query_result = {}
            network_name = network_descriptor["name"]
            cx = self.loaded_networks[network_descriptor["id"]]
            # --------------------------
            # Get Directed Paths
            path_query_result = \
                self.get_directed_paths_by_names(
                    query["source_names"],
                    query["target_names"],
                    cx
                    )
            path_node_names = self.get_path_node_names(path_query_result)
            query_result["forward_paths"] = path_query_result["forward_paths"]
            query_result["reverse_paths"] = path_query_result["reverse_paths"]

            # --------------------------
            # Get Cell Line Context for Nodes
            context_result = \
                self.get_mutation_context(path_node_names,
                                          list(query["cell_line"]))
            mutation_node_names = []

            # --------------------------
            # Get Directed Paths from Path Nodes to Mutation Nodes
            # (just use edges to adjacent mutations for now)
            # (skip mutation nodes already in paths)
            mutation_node_names_not_in_paths = \
                list(set(mutation_node_names).difference(set(path_node_names)))
            mutation_query_result = self.get_directed_paths_by_names(
                path_node_names,
                mutation_node_names_not_in_paths,
                cx
                )
            query_result["forward_mutation_paths"] = \
                mutation_query_result["forward_paths"]
            query_result["reverse_mutation_paths"] = \
                mutation_query_result["reverse_paths"]

            # --------------------------
            # Annotate path nodes based on mutation proximity, compute ranks.

            # --------------------------
            # Build, Format, Save Merged Network
            merged_network = None

            # --------------------------
            # Contrast and Annotate Canonical vs Novel Paths
            # Cannonical Paths
            # Novel Paths
            # Cannonical Paths not in general networks
            # Add summary to result

            query_results[network_name] = query_result

        # --------------------------
        # Save Query Results (except for network)
        self.save_query_results(query_results)

        return None

    # --------------------------
    #  Load Reference Networks

    # --------------------------
    #  Run Queries
    #
    # for query in queries:
    #     run_query(query)


class PathScoring():
    def __init__(self):
        self.mystr = ""

    def cross_country_scoring(self, A, B):
        A_scores = self.cx_edges_to_tuples(A, "A")
        B_scores = self.cx_edges_to_tuples(B, "B")

        average_finish = self.calculate_average_position(A_scores, B_scores)

        a_team_totals = 0.0
        b_team_totals = 0.0

        #=================================
        # DETERMINE TEAM TOTALS
        #=================================
        for k in average_finish.keys():
            for s in average_finish[k]:
                if s[:1] == "A":
                    a_team_totals += k
                else:
                    b_team_totals += k

        #print(a_team_totals)
        #print(b_team_totals)

        if a_team_totals > b_team_totals:
            return 1
        elif a_team_totals < b_team_totals:
            return -1
        else:
            return 0

    def calculate_average_position(self, A_scores, B_scores):
        '''
        Calculates the finish positions based on edge types

        :param A: Alternating nodes and edges i.e. [N1, E1, N2, E2, N3]
        :type A: Array
        :param B: Alternating nodes and edges i.e. [N1, E1, N2, E2, N3]
        :type B: Array
        :return: Finish positions
        :rtype: dict
        '''
        scores = A_scores + B_scores

        sorted_scores = sorted(scores, key=lambda x: x[1])
        res = {}
        prev = None
        for i, (k, v) in enumerate(sorted_scores):
            if v != prev:  # NEXT PLACE
                place, prev = i+1,v
            res[k] = place

        simple_finish_results = {}
        for k in res.keys():
            if simple_finish_results.get(res[k]) is None:
                simple_finish_results[res[k]] = [k]
            else:
                simple_finish_results[res[k]].append(k)

        average_finish = {}
        #==============================================
        # COMPUTE THE AVERAGE FINISH POSITION FOR TIES
        #==============================================
        for k in simple_finish_results.keys():
            finres = len(simple_finish_results[k])
            position_average = sum(range(k, k + finres)) / float(finres)
            average_finish[position_average] = simple_finish_results[k]

        return average_finish

    def cx_edges_to_tuples(self, p, prefix):
        '''
        Converts edge types to integer value.
        Edge types are ranked by the EdgeRanking class
        :param p:
        :type p:
        :param prefix:
        :type prefix:
        :return:
        :rtype:
        '''
        edge_ranking = EdgeRanking()
        path_tuples = []
        for i, multi_edges in enumerate(p):
            if i % 2 != 0:  # Odd elements are edges
                if len(multi_edges) > 0:
                    top_edge = None
                    tmp_multi_edges = None
                    if type(multi_edges) is dict:
                        tmp_multi_edges = \
                            self.convert_edge_dict_to_array(multi_edges)
                    else:
                        tmp_multi_edges = multi_edges

                    for edge in tmp_multi_edges:
                        if top_edge is None:
                            top_edge = edge
                        else:
                            if edge_ranking.edge_type_rank[edge.get("interaction")] < \
                               edge_ranking.edge_type_rank[top_edge.get("interaction")]:
                                top_edge = edge

                    path_tuples.append((prefix + str(i),
                        edge_ranking.edge_type_rank[top_edge.get("interaction")]))

        return path_tuples

    def convert_edge_dict_to_array(self, edge):
        '''
        Helper function to convert the raw edge dict
        to an array which is the format used in
        path scoring
        '''
        tmp_edge_list = []
        for e in edge.keys():

            tmp_edge_list.append(edge[e])

        return tmp_edge_list


class EdgeRanking(object):
    def __init__(self):
        self.edge_types = []

        self.edge_class_rank = {
            EdgeEnum.specific_protein_protein: [  # 1
                "controls-transport-of",
                "controls-phosphorylation-of",
                "Phosphorylation",
                "Dephosphorylation",
                "controls-transport-of-chemical",
                "consumption-controled-by",
                "controls-production-of",
                "Ubiquitination",
                "Deubiquitination",
                "Gef",
                "Gap"
            ],
            EdgeEnum.unspecified_activation_inhibition: [  # 2
                "Activation",
                "Inhibition",
                "GtpActivation"
            ],
            EdgeEnum.unspecified_state_control: [  # 3
                "controls-state-change-of",
                "chemical-affects"
            ],
            EdgeEnum.unspecified_direct: [  # 4
                "reacts-with",
                "used-to-produce"
            ],
            EdgeEnum.transcriptional_control: [  # 5
                "IncreaseAmount",
                "DecreaseAmount",
                "controls-expression-of",
                "Acetylation",
                "Deacetylation",
                "Sumoylation",
                "Desumoylation",
                "Ribosylation",
                "Deribosylation"
            ],
            EdgeEnum.proteins_catalysis_lsmr: [  # 6
                "catalysis-precedes"
            ],
            EdgeEnum.specific_protein_protein_undirected: [  # 7
                "in-complex-with",
                "Complex"
            ],
            EdgeEnum.non_specific_protein_protein_undirected: [  # 8
                "interacts-with"
            ],
            EdgeEnum.unspecified_topological:[  # 9
                "neighbor-of"
            ]
        }

        #===============================================
        # Generates a dict based on edge_class_rank
        # with edge types as key and rank int as value
        #===============================================
        self.edge_type_rank = {}

        for key in self.edge_class_rank.keys():
            for et in self.edge_class_rank[key]:
                if isinstance(key, int):
                    self.edge_type_rank[et] = key
                else:
                    self.edge_type_rank[et] = key.value

    def build_edge_type_list(self, edge_class_type_array):
        for ect in edge_class_type_array:
            if(type(ect) is EdgeEnum):
                for et in self.edge_class_rank[ect]:
                    if(et not in self.edge_types):
                        self.edge_types.append(et)

    def print_edge_types(self):
        for et in self.edge_types:
            print(et)


#==================================
# Enum Classes
#==================================
class EdgeEnum(Enum):
    specific_protein_protein = 1
    unspecified_activation_inhibition = 2
    unspecified_state_control = 3
    unspecified_direct = 4
    transcriptional_control = 5
    proteins_catalysis_lsmr = 6  # linked small molecule reactions
    specific_protein_protein_undirected = 7
    non_specific_protein_protein_undirected = 8
    unspecified_topological = 9

    def edge_count(self):
        return 9
