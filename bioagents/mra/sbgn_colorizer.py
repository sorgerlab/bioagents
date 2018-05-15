from lxml import etree
import os

class SbgnColorizer(object):
    """Adds border color and fill colors to an SBGNviz diagram via extensions
    supported by SBGNviz.

    Attributes
    ----------
    tree : lxml.etree.Element
        Root node for the XML tree of the current SBGN-ML document,
        incrementally modified with colors as functions of this object are
        called to do so
    """

    def __init__(self, sbgn_text):
        """Initializes colorizes with uncolorized sbgn generated from a pysb
        model.
        """
        self.sbgn_text = sbgn_text
        self.tree = etree.fromstring(sbgn_text)

    def get_nodes(self):
        """Returns the labels of the nodes that can be colorized;
        duplicate labels are possible."""
        pass

    def set_colors(self, label, border_color, fill_color):
        """Colorizes all nodes with the specified label with the specified
        border and fill color."""
        pass

if __name__ == '__main__':
    this_dir = os.path.dirname(__file__)
    path_test = os.path.join(this_dir, '..', 'tests', 'sbgn_color_test_files',
                             'original.sbgnml')
    with open(path_test, 'r') as f:
        content = f.read()

    colorizer = SbgnColorizer(content)
