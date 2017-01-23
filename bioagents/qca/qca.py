# DTDA stands for disease-target-drug agent whose task is to
# search for targets known to be implicated in a
# certain disease and to look for drugs that are known
# to affect that target directly or indirectly

import re
import os
import logging
#import rdflib
import sqlite3
import numpy
import operator
#from indra.statements import ActiveForm
#from indra.bel.processor import BelProcessor
from bioagents.databases import chebi_client
from bioagents.databases import cbio_client
from ndex.networkn import NdexGraph
import ndex.beta.toolbox as toolbox
import causal_utilities as cu
import json
import ndex.client as nc
from ndex.networkn import NdexGraph
import ndex
import requests
import io

logger = logging.getLogger('QCA')

_resource_dir = os.path.dirname(os.path.realpath(__file__)) + '/../resources/'

class DrugNotFoundException(Exception):
    def __init__(self, *args, **kwargs):
            Exception.__init__(self, *args, **kwargs)

class DiseaseNotFoundException(Exception):
    def __init__(self, *args, **kwargs):
            Exception.__init__(self, *args, **kwargs)

def _make_cbio_efo_map():
    lines = open(_resource_dir + 'cbio_efo_map.tsv', 'rt').readlines()
    cbio_efo_map = {}
    for lin in lines:
        cbio_id, efo_id = lin.strip().split('\t')
        try:
            cbio_efo_map[efo_id].append(cbio_id)
        except KeyError:
            cbio_efo_map[efo_id] = [cbio_id]
    return cbio_efo_map

cbio_efo_map = _make_cbio_efo_map()

class QCA:
    def __init__(self):
        logger.debug('Starting QCA')

        self.load_reference_networks()

    def __del__(self):
        print "deleting class"
        #self.drug_db.close()

    def find_causal_path(self, source_names, target_names, exit_on_found_path=False, relation_types=None):
        results_list = []

        #==========================================
        # Find paths in all available networks
        #==========================================
        for key in self.loaded_networks.keys():
            pr = self.get_directed_paths_by_names(source_names, target_names, self.loaded_networks[key], relation_types=relation_types)
            prc = pr.content
            if prc is not None and len(prc.strip()) > 0:
                try:
                    result_json = json.loads(prc)
                    if result_json.get('data') is not None:
                        if result_json.get("data").get("forward_english") is not None:
                            forward_english = result_json.get("data").get("forward_english")
                            for itm in forward_english:
                                print len(itm)
                            f_e = result_json.get("data").get("forward_english")
                            if len(f_e) > 0:
                                for f_e_i in f_e:
                                    results_list.append(f_e_i)
                                    if exit_on_found_path:
                                        return results_list
                except ValueError as ve:
                    print "value is not json.  html 500?"

        results_list_sorted = sorted(results_list, lambda x,y: 1 if len(x)>len(y) else -1 if len(x)<len(y) else 0)

        print results_list_sorted[:2]
        print results_list[:2]
        return results_list_sorted[:2]

    def has_path(self, source_names, target_names):
        found_path = self.find_causal_path(source_names, target_names, exit_on_found_path=True)

        return len(found_path) > 0

    #TODO reorg code
    # --------------------------
    # NDEx and Services

    host = "http://www.ndexbio.org"
    username = "drh"
    password = "drh"
    ndex = nc.Ndex(host=host, username=username, password=password)

    # --------------------------
    # Schemas

    query_result_schema = {
        "network_description": {},
        "forward_paths": [],
        "reverse_paths": [],
        "forward_mutation_paths": [],
        "reverse_mutation_paths": []
    }

    reference_network_schema = {
        "id": "",
        "name": "",
        "type": "cannonical"
    }

    query_schema = {
        "source_names": [],
        "target_names": [],
        "cell_line": ""
    }

    # --------------------------
    #  Globals

    results_directory = "qca_results"

    #directed_path_query_url = 'http://ec2-52-37-182-174.us-west-2.compute.amazonaws.com:5603/directedpath/query'
    directed_path_query_url = 'http://general.bigmech.ndexbio.org:5603/directedpath/query'
    #directed_path_query_url = 'http://localhost:5603/directedpath/query'


    context_expression_query_url = 'http://general.bigmech.ndexbio.org:8081/context/expression/cell_line'

    context_mutation_query_url = url = 'http://general.bigmech.ndexbio.org:8081/context/mutation/cell_line'

    # dict of reference network descriptors by network name
    reference_networks = [
        {
            "id": "09f3c90a-121a-11e6-a039-06603eb7f303",
            "name": "NCI Pathway Interaction Database - Final Revision - Extended Binary SIF",
            "type": "cannonical"
        }
    ]

    reference_networks_full = [
        {
            "id": "5294f70b-618f-11e5-8ac5-06603eb7f303",
            "name": "Calcium signaling in the CD4 TCR pathway",
            "type": "cannonical"
        },
        {
            "id": "5e904cd6-6193-11e5-8ac5-06603eb7f303",
            "name": "IGF1 pathway",
            "type": "cannonical"
        },
        {
            "id": "20ef2b81-6193-11e5-8ac5-06603eb7f303",
            "name": "HIF-1-alpha transcription factor network ",
            "type": "cannonical"
        },
        {
            "id": "ac39d2b9-6195-11e5-8ac5-06603eb7f303",
            "name": "Signaling events mediated by Hepatocyte Growth Factor Receptor (c-Met)",
            "type": "cannonical"
        },
        {
            "id": "d3747df2-6190-11e5-8ac5-06603eb7f303",
            "name": "Ceramide signaling pathway",
            "type": "cannonical"
        },
        {
            "id": "09f3c90a-121a-11e6-a039-06603eb7f303",
            "name": "NCI Pathway Interaction Database - Final Revision - Extended Binary SIF",
            "type": "cannonical"
        }
    ]


    # dict of available network CX data by name
    loaded_networks = {}

    # --------------------------
    #  Cell Lines

    cell_lines = []

    # --------------------------
    #  Queries

    # list of query dicts
    queries = []


    # --------------------------
    # Functions

    def load_reference_networks(self):
        for rn in self.reference_networks_full:
            if "id" in rn and "name" in rn:
                result = self.ndex.get_network_as_cx_stream(rn["id"])
                self.loaded_networks[rn["name"]] = result.content #json.loads(result.content)
            else:
                raise Exception("reference network descriptors require both name and id")

    def get_directed_paths_by_names(self, source_names, target_names, reference_network_cx, max_number_of_paths=5, relation_types=None):
        target = " ".join(target_names)
        source = " ".join(source_names)
        if relation_types is not None:
            rts = " ".join(relation_types)
            url = self.directed_path_query_url + '?source=' + source + '&target=' + target + '&pathnum=' + str(max_number_of_paths) + '&relationtypes=' + rts
        else:
            url = self.directed_path_query_url + '?source=' + source + '&target=' + target + '&pathnum=' + str(max_number_of_paths)

        #print url
        f = io.BytesIO()
        f.write(reference_network_cx)
        f.seek(0)
        r = requests.post(url, files={'network_cx': f})
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
        json.dump(query_results,outfile, indent=4)
        outfile.close()

    def get_mutation_paths(self, query_result, mutated_nodes, reference_network):
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
            path_query_result = self.get_directed_paths_by_names(query["source_names"], query["target_names"], cx)
            path_node_names = self.get_path_node_names(path_query_result)
            query_result["forward_paths"] = path_query_result["forward_paths"]
            query_result["reverse_paths"] = path_query_result["reverse_paths"]

            # --------------------------
            # Get Cell Line Context for Nodes
            context_result = self.get_mutation_context(path_node_names, list(query["cell_line"]))
            mutation_node_names = []

            # --------------------------
            # Get Directed Paths from Path Nodes to Mutation Nodes
            # (just use edges to adjacent mutations for now)
            # (skip mutation nodes already in paths)
            mutation_node_names_not_in_paths = list(set(mutation_node_names).difference(set(path_node_names)))
            mutation_query_result = self.get_directed_paths_by_names(path_node_names, mutation_node_names_not_in_paths, cx)
            query_result["forward_mutation_paths"] = mutation_query_result["forward_paths"]
            query_result["reverse_mutation_paths"] = mutation_query_result["reverse_paths"]

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










class DirectedPaths:

    def __init__(self):
        logging.info('DirectedPaths: Initializing')

        logging.info('DirectedPaths: Initialization complete')

    def findPaths(self, network_id, source_list, target_list, ndex_server="http://public.ndexbio.org",
                  rm_username="test",rm_password="test",npaths=20, network_name="Directed Path Network"):
        print "in paths"

        G = NdexGraph(server=ndex_server, uuid=network_id, username=rm_username, password=rm_password)

        # Compute the source-target network
        P1 = cu.get_source_target_network(G, source_list, target_list, network_name, npaths=npaths)

        # Apply a layout
        toolbox.apply_source_target_layout(P1.get('network'))

        # Apply a cytoscape style from a template network
        template_id = '4f53171c-600f-11e6-b0a6-06603eb7f303'
        toolbox.apply_template(P1.get('network'), template_id)

        return {'forward': P1.get('forward'), 'reverse': P1.get('reverse'), 'network': P1.get('network').to_cx()}

    def findDirectedPaths(self, network_cx,source_list,target_list,npaths=20):
        print "in paths"

        G = NdexGraph(cx=network_cx)

        # Compute the source-target network
        P1 = cu.get_source_target_network(G, source_list, target_list, "Title placeholder", npaths=npaths)

        # Apply a layout
        #toolbox.apply_source_target_layout(P1.get('network'))

        # Apply a cytoscape style from a template network
        template_id = '4f53171c-600f-11e6-b0a6-06603eb7f303'
        #toolbox.apply_template(P1.get('network'), template_id)

        #TODO: Process the forward and reverse lists.  Generate [{node1},{edge1},{node2},{edge2},etc...]

        F = P1.get('forward')
        R = P1.get('reverse')
        G_prime = P1.get('network')

        new_forward_list = self.label_node_list(F, G, G_prime)

        return {'forward': P1.get('forward'), 'forward_english': new_forward_list, 'reverse': P1.get('reverse'), 'network': P1.get('network').to_cx()}

    def label_node_list(self, n_list, G, G_prime):
        outer = []
        for f in n_list:
            inner = []
            #====================================
            # Take an array of nodes and fill in
            # the edge between the nodes
            #====================================
            for first, second in zip(f, f[1:]):
                this_edge = G_prime.edge.get(first).get(second)
                print G.get_edge_data(first,second)

                if(this_edge is not None):
                    if(len(inner) < 1):
                        inner.append(G_prime.node.get(first).get('name'))

                    inner.append(G.get_edge_data(first,second))
                    inner.append(G_prime.node.get(second).get('name'))

            outer.append(inner)

        return outer

class Disease(object):
    def __init__(self, disease_type, name, db_refs):
        self.disease_type = disease_type
        self.name = name
        self.db_refs = db_refs

    def __repr__(self):
        return 'Disease(%s, %s, %s)' % \
            (self.disease_type, self.name, self.db_refs)

    def __str__(self):
        return self.__repr__()


