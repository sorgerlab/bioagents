from lxml import etree
import os
from collections import namedtuple

# How a node should be colorized
Style = namedtuple('Style', ['border_color', 'fill_color'])

class SbgnColorizer(object):
    """Adds border color and fill colors to an SBGNviz diagram via extensions
    supported by SBGNviz.

    Attributes
    ----------
    root : lxml.etree.Element
        Root node for the XML tree of the original SBGN-ML document,
        incrementally modified with colors as functions of this object are
        called to do so
    glyph_id_to_label : dict
        Dictionary mapping the glyph id to the corresponding label for each
        element in the original sbgn-ml
    label_to_style : dict
        For each node for which a non-default style is desired, a mapping
        from the node's label to the node's style
    """

    def __init__(self, sbgn_text):
        """Initializes colorizes with uncolorized sbgn generated from a pysb
        model.

        Parameters
        ----------
        sbgn_text: str
            The XML text of the original uncolorized SBGN-ML document generated
            from a pySB model
        """
        self.label_to_style = {}
        self.sbgn_text = sbgn_text
        self.root = etree.fromstring(sbgn_text)

        # Create a dictionary mapping glyph ids to the corresponding label
        # More than one glyph might have the same label
        self.glyph_id_to_label = {}
        last_id = None
        for element in self.root.iter():
            if element.tag.endswith('glyph'):
                last_id = element.get('id')
            elif element.tag.endswith('label'):
                if last_id is not None:
                    label = element.get('text')
                    if label is not None:
                        self.glyph_id_to_label[last_id] = label

    def get_nodes(self):
        """Returns the labels of the nodes that can be colorized;
        duplicate labels are possible.

        Returns
        -------
        labels: set<str>
            The labels of the nodes in the diagram
        """
        return set(self.glyph_id_to_label.values())

    def set_style(self, label, border_color, fill_color):
        """Colorizes all nodes with the specified label with the specified
        border and fill color.

        Parameters
        ----------
        label : str
            Add a styel to nodes with this label
        border_color : str
            The border color, starting with # and followed by six hex digits
        fill_color : str
            The fill color, starting with # and followed by six hex digits
        """
        assert(border_color.startswith('#'))
        assert(fill_color.startswith('#'))
        self.label_to_style[label] = Style(border_color, fill_color)

    def generate_xml(self):
        """Generates XML that colorizes the nodes previously specified with
        set_style.

        Returns
        -------
        xml: str
            SBGM-ML XML with extension notation understandable by SBGNviz
            giving the colorign for the specified nodes
        """
        pass

if __name__ == '__main__':
    this_dir = os.path.dirname(__file__)
    path_test = os.path.join(this_dir, '..', 'tests', 'sbgn_color_test_files',
                             'original.sbgnml')
    with open(path_test, 'r') as f:
        content = f.read()

    colorizer = SbgnColorizer(content)
    print(colorizer.glyph_id_to_label)
    colorizer.set_style('RAF', '#ff0000', '#00ff00')
