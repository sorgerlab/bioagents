import unittest
from qca_module import QCA_Module

class MyTestCase(unittest.TestCase):
    def test_something(self):
        qca_module_instance = QCA_Module()
        qca_module_instance.receive_request("find-qca-path", "(FIND-QCA-PATH : TARGET 'NFKB,ATK1')")

        self.assertEqual(True, True)


if __name__ == '__main__':
    unittest.main()
