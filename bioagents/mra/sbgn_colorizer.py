from lxml import etree
import os
import re
import json
import copy
import logging
import collections
from matplotlib import cm
from matplotlib import colors

from indra.sources.indra_db_rest import get_statements
from indra.ontology.bio import bio_ontology
from indra.databases import context_client
from indra.assemblers.pysb.assembler import _n


logger = logging.getLogger('sbgn_colorizer')

# How a node should be colorized
Style = collections.namedtuple('Style', ['border_color', 'fill_color'])


def is_mutation_activating(gene_name, mutation_status):
    """Checks the database for whether a mutation is activating.

    Parameters
    ----------
    agent_name: str
        The name of the gene
    mutation_status: list<str>
        Mutations

    Returns
    -------
    is_activing: bool
        True if the database says the mutation is activating, False if the
        database says the mutation is inhibiting, None if the database doesn't
        say
    """
    ip = get_statements(agents=[gene_name], stmt_type='ActiveForm')
    print('ActiveForm statements involving', gene_name)
    for statement in ip.statements:
        print(statement)


class SbgnColorizer(object):
    """Adds border color and fill colors to an SBGNviz diagram via extensions
    supported by SBGNviz.

    Attributes
    ----------
    root : lxml.etree.Element
        Root node for the XML tree of the original SBGN-ML document,
        incrementally modified with colors as functions of this object are
        called to do so
    glyph_ids: set
        All glyph ids (whether for nodes, processes, etc)
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
        self.element_ids = set()
        self.label_to_glyph_ids = collections.defaultdict(set)
        last_id = None
        for element in self.root.iter():
            if element.tag.endswith('glyph'):
                last_id = element.get('id')
                self.element_ids.add(last_id)
            elif element.tag.endswith('label'):
                if last_id is not None:
                    label = element.get('text')  # May be None or empty
                    self.label_to_glyph_ids[label].add(last_id)

        # Add ids from non-glyph top-level children
        for element in self.root[0]:
            if 'id' in element.attrib:
                self.element_ids.add(element.attrib['id'])

        # Load caches
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '../resources/expression_cache.json'), 'r') as fh:

            self.expr = json.load(fh)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '../resources/mutation_cache.json'), 'r') as fh:
            self.mut = json.load(fh)

    def get_nodes(self):
        """Returns the labels of the nodes that can be colorized;
        duplicate labels are possible.

        Returns
        -------
        labels: set<str>
            The labels of the nodes in the diagram
        """
        return set(self.label_to_glyph_ids.keys())

    def ids_without_specified_style(self):
        """Returns a list of ids without a specified style.

        Returns
        -------
        ids: list<str>
            A list of glyph ids for which no style has been specified with
            set_style
        """
        styled_ids = set()
        for label, id_list in self.label_to_glyph_ids.items():
            if label in self.label_to_style:
                styled_ids.update(id_list)
        return self.element_ids.difference(styled_ids)

    def set_style(self, label, border_color, fill_color):
        """Colorizes all nodes with the specified label with the specified
        border and fill color.

        Parameters
        ----------
        label : str
            Add a style to nodes with this label
        border_color : str
            The border color, starting with # and followed by six hex digits
        fill_color : str
            The fill color, starting with # and followed by six hex digits
        """
        label = _n(label)
        assert(border_color.startswith('#'))
        assert(fill_color.startswith('#'))
        labels = self.label_to_glyph_ids.keys()
        if label in labels:
            self.label_to_style[label] = Style(border_color, fill_color)

    def get_mutations(self, gene, cell_line):
        if cell_line in self.mut:
            mut = self.mut[cell_line].get(gene, [])
            return {cell_line: {gene: mut}}
        else:
            return context_client.get_mutations([gene], [cell_line])

    def get_expression(self, genes, cell_line):
        if cell_line in self.expr:
            ret = {cell_line: {g: None for g in genes}}
            for gene in genes:
                ret[cell_line][gene] = self.expr[cell_line].get(gene, None)
            return ret
        else:
            return context_client.get_protein_expression(genes, [cell_line])

    def _choose_stroke_color_from_mutation_status(self, gene_name, cell_line):
        """Chooses the stroke color based on whether the gene is mutated
        in the given cell line.

        Parameters
        ----------
        gene_name: str
            The name of the gene
        cell_line: str
            The name of the cell line

        Returns
        -------
        color: str
            The hex color string for the chosen stroke color
        """
        logger.info('Getting mutation status of proteins')
        mut_statuses = self.get_mutations(gene_name, cell_line)
        assert len(mut_statuses.keys()) == 1, mut_statuses

        mut_status = mut_statuses[cell_line][gene_name]

        # Remove this for now to avoid DB query
        # if len(mut_status) > 0:
        #   is_activating = is_mutation_activating(gene_name, mut_status)

        if len(mut_status) > 0:
            return '#ff0000'
        else:
            return '#555555'

    def set_style_expression_mutation(self, model, cell_line='A375_SKIN'):
        """Sets the fill color of each node based on its expression level
        on the given cell line, and the stroke color based on whether it is
        a mutation.

        Parameters
        ----------
        model: list<indra.statements.Statement>
            A list of INDRA statements
        cell_line: str
            A cell line for which we're interested in protein expression level
        """
        labels = self.label_to_glyph_ids.keys()

        label_to_agent = {}
        for label in labels:
            for statement in model:
                for agent in statement.agent_list():
                    if agent is not None and _n(agent.name) == label:
                        label_to_agent[label] = agent

        agent_to_expression_level = {}
        for agent in label_to_agent.values():
            if 'HGNC' not in agent.db_refs and 'FPLX' not in agent.db_refs:
                # This is not a gene
                agent_to_expression_level[agent] = 0
                continue

            if 'FPLX' not in agent.db_refs:
                gene_names = [agent.name]
            else:
                children = bio_ontology.get_children('FPLX',
                                                     agent.db_refs['FPLX'])
                gene_names = [bio_ontology.get_name(*child) for child
                              in children]

            # Compute mean expression level
            expression_levels = []
            logger.info('Getting expression status of proteins: %s' %
                        str(gene_names))
            l = self.get_expression(gene_names, cell_line)
            for line in l:
                for element in l[line]:
                    level = l[line][element]
                    if level is not None:
                        expression_levels.append(l[line][element])
            if len(expression_levels) == 0:
                mean_level = None
            else:
                mean_level = sum(expression_levels) / len(expression_levels)

            agent_to_expression_level[agent] = mean_level

        # Create a normalized expression score between 0 and 1
        # Compute min and maximum levels
        min_level = None
        max_level = None
        for agent, level in agent_to_expression_level.items():
            if level is None:
                continue
            if min_level is None:
                min_level = level
            if max_level is None:
                max_level = level
            if level < min_level:
                min_level = level
            if level > max_level:
                max_level = level
        # Compute scores
        agent_to_score = {}
        if max_level is not None:
            level_span = max_level - min_level
        for agent, level in agent_to_expression_level.items():
            if level is None or level_span == 0:
                agent_to_score[agent] = 0
            else:
                agent_to_score[agent] = (level - min_level) / level_span

        # Map scores to colors and assign colors to labels
        agent_to_color = {}
        for agent, score in agent_to_score.items():
            if 'HGNC' not in agent.db_refs and 'FPLX' not in agent.db_refs:
                color = cm.Blues(0.3)
                color_str = colors.to_hex(color[:3])
            else:
                # color = cm.plasma(score)
                color = cm.Greens(0.6*score + 0.2)
                color_str = colors.to_hex(color[:3])
            assert(len(color_str) == 7)
            stroke_color = \
                    self._choose_stroke_color_from_mutation_status(agent.name,
                                                                   cell_line)
            self.set_style(agent.name, stroke_color, color_str)

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
        id_number = 2
        for color in all_colors:
            id_str = 'color_' + str(id_number)
            color_to_id[color] = id_str
            id_number += 1

        # Encode each color and its corresponding id as XML
        list_of_color_definitions = etree.Element('listOfColorDefinitions')
        # Default stroke
        color_def_default_stroke = etree.Element('colorDefinition')
        color_def_default_stroke.attrib['id'] = 'color_1'
        color_def_default_stroke.attrib['value'] = '#555555'
        list_of_color_definitions.append(color_def_default_stroke)
        # Default fill
        # color_def_default_fill = etree.Element('colorDefinition')
        # color_def_default_fill.attrib['id'] = 'color_default_fill'
        # color_def_default_fill.attrib['value'] = '#ffffff7f'
        # list_of_color_definitions.append(color_def_default_fill)
        # Custom colors
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
        style_id_number = 2
        for label, style in self.label_to_style.items():
            style_id_str = 'style_' + str(style_id_number)
            style_to_id[style] = style_id_str
            style_id_number += 1
            style_to_assigned_labels[style].add(label)

        # Encode each style and the nodes that use it as XML
        list_of_styles = etree.Element('listOfStyles')
        # Default style
        default_style = etree.Element('style')
        default_style.attrib['id'] = 'style_1'
        default_style.attrib['idList'] = \
                ' '.join(self.ids_without_specified_style())
        default_g = etree.Element('g')
        default_g.attrib['stroke'] = 'color_1'
        default_g.attrib['strokeWidth'] = '1.25'
        # default_g.attrib['fill'] = 'color_default_fill'
        default_style.append(default_g)
        list_of_styles.append(default_style)
        # Custom styules
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

            if len(style_xml.attrib['idList']) > 0:
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
        <adjustNodeLabelFontSizeAutomatically>false
        </adjustNodeLabelFontSizeAutomatically>
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
        root_copy[0].insert(0, extension)
        xml_txt = etree.tostring(root_copy, pretty_print=True).decode('utf-8')
                                 #encoding='UTF-8', standalone=True).decode(
                                 #        'utf-8')

        # Change the namespace
        ns_re = """xmlns=['"][^'"]+['"]"""
        xml_txt = re.sub(ns_re, 'xmlns="http://sbgn.org/libsbgn/0.3"', xml_txt)

        with open('xml_txt.xml', 'w') as f:
            f.write(xml_txt)

        return xml_txt
