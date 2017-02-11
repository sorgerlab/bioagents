import unittest
#from qca_module import QCA_Module
#from qca import QCA
#from qca import EdgeRanking, EdgeEnum
from lispify_helper import Lispify
import ndex.client as nc
#import io
import requests
from ndex.beta.path_scoring import PathScoring
import json

class MyTestCase(unittest.TestCase):
    def test_something(self):
        #qca = QCA()
        #  source_names = ["CALM3"]
        #  target_names = ["NFATC2"]

        source_names = ["AKT1", "AKT2", "AKT3"]
        target_names = ["CCND1","CDKN1A","FOXO3","GSK3B","MAP2K1","MAPK3","MTOR","PARP1","PIK3CA","RICTOR","TP53"]

        #AKT1
        #AKT1S1
        #AKT2
        #AKT3

        results_list = []  # qca.find_causal_path(source_names, target_names, relation_types=None)  # ["Activation", "controls-state-change-of", "in-complex-with", "controls-transport-of", "controls-phosphorylation-of"])
        print "results_list:"
        print results_list
        host = "http://www.ndexbio.org"
        directed_path_query_url = 'http://general.bigmech.ndexbio.org/directedpath/query'
        #directed_path_query_url = 'http://localhost:5603/directedpath/query'

        ndex = nc.Ndex(host=host)

        #reference_network_cx = ndex.get_network_as_cx_stream("5294f70b-618f-11e5-8ac5-06603eb7f303")

        #====================
        # Assemble REST url
        #====================
        uuid_prior = "84f321c6-dade-11e6-86b1-0ac135e8bacf"
        uuid_high_confidence = "b04e406b-dc88-11e6-86b1-0ac135e8bacf"
        target = ",".join(target_names)
        source = ",".join(source_names)
        max_number_of_paths = 50
        url = directed_path_query_url + '?source=' + source + '&target=' + target + '&uuid=' + uuid_prior + '&server=www.ndexbio.org' + '&pathnum=' + str(max_number_of_paths)

        #f = io.BytesIO()
        #f.write(reference_network_cx.content)
        #f.seek(0)
        #r = requests.post(url, files={'network_cx': f})
        r = requests.post(url)
        '''
        r1 = requests.post(url)
        r2 = requests.post(url)
        r3 = requests.post(url)
        r4 = requests.post(url)
        r5 = requests.post(url)
        r6 = requests.post(url)
        r7 = requests.post(url)
        r8 = requests.post(url)
        '''

        result_json = json.loads(r.content)

        edge_results = result_json.get("data").get("forward_english")
        path_scoring = PathScoring()

        A_all_scores = []

        for i, edge in enumerate(edge_results):
            print len(edge)
            top_edge = None
            if i == 24:
                mystr = ""
            if i == 14:
                mystr = ""
            for ranked_edges in path_scoring.cx_edges_to_tuples(edge, "A"):
                if top_edge is None:
                    top_edge = ranked_edges
                else:
                    if ranked_edges[1] < top_edge[1]:
                        top_edge = ranked_edges

            A_all_scores.append(("A" + str(i), top_edge[1]))

        #('A0', [('A1', 1)])

        print A_all_scores
        race_results = path_scoring.calculate_average_position(A_all_scores,[])

        print race_results

        #print r.content

        '''
        print r1.content
        print r2.content
        print r3.content
        print r4.content
        print r5.content
        print r6.content
        print r7.content
        print r8.content
        '''
        #lispify_helper = Lispify(results_list)

        #path_statements = lispify_helper.to_lisp()

        print results_list

        self.assertEqual(True, True)

    def test_cross_country_scoring(self):
        paths = [
          [
            "PRH1",
            [
              {
                "polarity": "positive",
                "interaction": "Activation",
                "INDRA statement": "Activation(PRH1(), NOX1())",
                "Text": "Effect of AG1478 on PA induced NOX activity.",
                "Belief score": "1.00",
                "type": "Activation"
              }
            ],
            "NOX1"
          ],
          [
            "PRH1",
            [
              {
                "polarity": "positive",
                "interaction": "Activation",
                "INDRA statement": "Activation(PRH1(), INSR())",
                "Text": "We have known that PINK1 might alleviate PA induced IR in HepG2 cells.",
                "Belief score": "0.99",
                "type": "Activation"
              }
            ],
            "INSR",
            [
              {
                "polarity": "positive",
                "interaction": "Phosphorylation",
                "INDRA statement": "Activation(INSR(), ROS1())",
                "Text": "I/R injury triggers a series of ROS, proinflammatory cytokines and chemotactic cytokines XREF_BIBR, XREF_BIBR.",
                "Belief score": "0.99",
                "type": "Activation"
              },
              {
                "interaction": "Activation"
              }
            ],
            "ROS1",
            [
              {
                "interaction": "Activation"
              }
            ],
            "NOX1"
          ]
        ]

        path_scoring = PathScoring()
        #for path_count, p in enumerate(paths):
        #    print "path count %d" %path_count
            #print hash(frozenset(p))
            #=================================
            # PROCESS PATH
            #=================================
            #path_tuples = path_scoring.cx_edges_to_tuples(p, "A")

            #print path_tuples

        #edge_ranking = EdgeRanking()
        #et = [
        #    EdgeEnum.specific_protein_protein,
        #    EdgeEnum.proteins_catalysis_lsmr
        #]
        #edge_ranking.build_edge_type_list(et)
        #edge_ranking.print_edge_types()
        #self.assertEqual(res.get("A1"), )



        scores = [
        ('A1', 1),
        ('B1', 1),
        ('A2', 3),
        ('B2', 3),
        ('A3', 4),
        ('B3', 4),
        ('A4', 4),
        ('B4', 3),
        ('A5', 4),
        ('B5', 4),
        ('A6', 5)
        ]

        A = [
            "PRH1",
            [
              {
                "polarity": "positive",
                "interaction": "Activation",
                "INDRA statement": "Activation(PRH1(), NOX1())",
                "Text": "Effect of AG1478 on PA induced NOX activity.",
                "Belief score": "1.00",
                "type": "Activation"
              }
            ],
            "NOX1"
          ]

        B = [
            "PRH1",
            [
              {
                "polarity": "positive",
                "interaction": "Activation",
                "INDRA statement": "Activation(PRH1(), INSR())",
                "Text": "We have known that PINK1 might alleviate PA induced IR in HepG2 cells.",
                "Belief score": "0.99",
                "type": "Activation"
              }
            ],
            "INSR",
            [
              {
                "polarity": "positive",
                "interaction": "Phosphorylation",
                "INDRA statement": "Activation(INSR(), ROS1())",
                "Text": "I/R injury triggers a series of ROS, proinflammatory cytokines and chemotactic cytokines XREF_BIBR, XREF_BIBR.",
                "Belief score": "0.99",
                "type": "Activation"
              },
              {
                "interaction": "Activation"
              }
            ],
            "ROS1",
            [
              {
                "interaction": "Activation"
              }
            ],
            "NOX1"
          ]


        #print path_scoring.cross_country_scoring(A, B)
        '''
        sorted_scores = sorted(scores, lambda x,y: 1 if x[1] > y[1] else -1 if x[1] < y[1] else 0)

        res = {}
        prev = None
        for i,(k,v) in enumerate(sorted_scores):
            if v!=prev:  # NEXT PLACE
                place,prev = i+1,v
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
            position_average = float(sum(range(k, k + len(simple_finish_results[k])))) / float(len(simple_finish_results[k]))
            average_finish[position_average] = simple_finish_results[k]

        print average_finish

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

        print a_team_totals
        print b_team_totals


        self.assertEqual(res.get("A1"), 1)
        self.assertEqual(res.get("B1"), 1)
        self.assertEqual(res.get("A2"), 3)
        self.assertEqual(res.get("B2"), 3)
        self.assertEqual(res.get("B4"), 3)
        self.assertEqual(res.get("A3"), 6)
        self.assertEqual(res.get("B3"), 6)
        self.assertEqual(res.get("A4"), 6)
        self.assertEqual(res.get("A5"), 6)
        self.assertEqual(res.get("B5"), 6)
        '''
        self.assertTrue(True)

    def test_edge_type_classes(self):
        #edge_ranking = EdgeRanking()
        #et = [
        #    EdgeEnum.specific_protein_protein,
        #    EdgeEnum.proteins_catalysis_lsmr
        #]
        #edge_ranking.build_edge_type_list(et)
        #edge_ranking.print_edge_types()
        #self.assertEqual(res.get("A1"), )

        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
