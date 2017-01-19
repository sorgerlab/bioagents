import unittest
#from qca_module import QCA_Module
from qca import QCA

class MyTestCase(unittest.TestCase):
    def test_something(self):
        qca = QCA()
        source_names = ["IRS1"]
        target_names = ["SHC1"]
        results_list = qca.find_causal_path(source_names, target_names)

        print results_list
        #qca_module_instance = QCA_Module()
        #qca_module_instance.receive_request("find-qca-path", "(FIND-QCA-PATH : TARGET 'NFKB,ATK1')")

        self.assertEqual(True, True)


if __name__ == '__main__':
    unittest.main()
