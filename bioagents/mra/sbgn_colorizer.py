from lxml import etree
import os
import collections
import copy

# How a node should be colorized
Style = collections.namedtuple('Style', ['border_color', 'fill_color'])

class SbgnColorizer(object):
    """Adds border color and fill colors to an SBGNviz diagram via extensions
    supported by SBGNviz.

    Attributes
    ----------
    root : lxml.etree.Element
        Root node for the XML tree of the original SBGN-ML document,
        incrementally modified with colors as functions of this object are
        called to do so
    label_to_glyph_ids : dict
        Dictionary mapping a label to the set of glyph ids that have that label
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

        self.parser = etree.XMLParser(remove_blank_text=True)
        self.root = etree.fromstring(sbgn_text, self.parser)

        # Create a dictionary mapping glyph ids to the corresponding label
        # More than one glyph might have the same label
        self.label_to_glyph_ids = collections.defaultdict(set)
        last_id = None
        for element in self.root.iter():
            if element.tag.endswith('glyph'):
                last_id = element.get('id')
            elif element.tag.endswith('label'):
                if last_id is not None:
                    label = element.get('text')
                    if label is not None:
                        self.label_to_glyph_ids[label].add(last_id)

    def get_nodes(self):
        """Returns the labels of the nodes that can be colorized;
        duplicate labels are possible.

        Returns
        -------
        labels: set<str>
            The labels of the nodes in the diagram
        """
        return set(self.label_to_glyph_ids.keys())

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
        # Generate a list of all colors used
        all_colors = set()
        for label, style in self.label_to_style.items():
            border_color = style.border_color
            fill_color = style.fill_color

            all_colors.add(border_color)
            all_colors.add(fill_color)

        # Assign each color and style an id
        color_to_id = {}
        id_number = 1
        for color in all_colors:
            id_str = 'color_' + str(id_number)
            color_to_id[color] = id_str
            id_number += 1

        # Encode each color and its corresponding id as XML
        list_of_color_definitions = etree.Element('listOfColorDefinitions')
        for color, color_id in color_to_id.items():
            color_definition = etree.Element('colorDefinition')
            color_definition.attrib['id'] = color_id
            color_definition.attrib['value'] = color
            #
            list_of_color_definitions.append(color_definition)

        # Assign each style an id, and tabulate the nodes each style
        # is assigned to
        style_to_id = {}
        style_to_assigned_labels = collections.defaultdict(set)
        style_id_number = 1
        for label, style in self.label_to_style.items():
            style_id_str = 'style_' + str(style_id_number)
            style_to_id[style] = style_id_str
            style_id_number += 1
            style_to_assigned_labels[style].add(label)

        # Encode each style and the nodes that use it as XML
        list_of_styles = etree.Element('listOfStyles')
        for style, style_id in style_to_id.items():
            style_xml = etree.Element('style')
            style_xml.attrib['id'] = style_id
            label_list = style_to_assigned_labels[style]
            id_list = set()
            for label in label_list:
                id_list.update(self.label_to_glyph_ids[label])
            style_xml.attrib['idList'] = ' '.join(id_list)

            g = etree.Element('g')
            g.attrib['fontSize'] = '11'
            g.attrib['fontFamily'] = 'Helvetica'
            g.attrib['fontWeight'] = 'normal'
            g.attrib['fontStyle'] = 'normal'
            g.attrib['stroke'] = color_to_id[style.border_color]
            g.attrib['strokeWidth'] = '1.25'
            g.attrib['fill'] = color_to_id[style.fill_color]
            style_xml.append(g)

            list_of_styles.append(style_xml)

        # Create an extension element giving the coloring information
        extension = etree.Element('extension')
        render_info = etree.Element('renderInformation')
        render_info.attrib['xmlns'] ="http://www.sbml.org/sbml/level3/version1/render/version1"
        render_info.attrib['id'] = "renderInformation"
        render_info.attrib['programName'] = "sbgnviz"
        render_info.attrib['programVersion'] = "4.0.2"
        render_info.attrib['backgroundColor'] = "#000000"

        render_info.append(list_of_color_definitions)
        render_info.append(list_of_styles)
        extension.append(render_info)

        # Add map properties
        map_properties = """<mapProperties>
        <compoundPadding>10</compoundPadding>
        <extraCompartmentPadding>14</extraCompartmentPadding>
        <extraComplexPadding>10</extraComplexPadding>
        <arrowScale>1.25</arrowScale>
        <showComplexName>true</showComplexName>
        <dynamicLabelSize>regular</dynamicLabelSize>
        <fitLabelsToNodes>false</fitLabelsToNodes>
        <fitLabelsToInfoboxes>false</fitLabelsToInfoboxes>
        <rearrangeAfterExpandCollapse>true</rearrangeAfterExpandCollapse>
        <animateOnDrawingChanges>true</animateOnDrawingChanges>
        <adjustNodeLabelFontSizeAutomatically>false</adjustNodeLabelFontSizeAutomatically>
        <enablePorts>true</enablePorts>
        <allowCompoundNodeResize>false</allowCompoundNodeResize>
        <mapColorScheme>black_white</mapColorScheme>
        <defaultInfoboxHeight>12</defaultInfoboxHeight>
        <defaultInfoboxWidth>30</defaultInfoboxWidth>
        <mapName/>
        <mapDescription/>
        </mapProperties>"""
        extension.append(etree.fromstring(map_properties, self.parser))

        # Generate an SBGN-ML document with this extension information
        root_copy = copy.deepcopy(self.root)
        root_copy.attrib['xmlns'] = 'http://sbgn.org/libsbgn/0.3'
        root_copy[0].insert(0, extension)
        return etree.tostring(root_copy, pretty_print=True).decode('utf-8')

if __name__ == '__main__':
    this_dir = os.path.dirname(__file__)
    path_test = os.path.join(this_dir, '..', 'tests', 'sbgn_color_test_files',
                             'original.sbgnml')
    with open(path_test, 'r') as f:
        content = f.read()

    colorizer = SbgnColorizer(content)
    colorizer.set_style('RAF', '#ff0000', '#00ff00')
    print(colorizer.generate_xml())
