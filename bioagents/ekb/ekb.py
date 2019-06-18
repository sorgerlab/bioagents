from lxml import etree
from kqml import KQMLList
from indra.sources.trips.processor import TripsProcessor


class EKB(object):
    def __init__(self, graph, term_node):
        self.graph = graph
        self.graph.draw('test.pdf')
        self.root_term = term_node
        self.ekb = None
        self.components = [term_node]
        self.build()

    def build(self):
        self.ekb = etree.Element('ekb')
        # Determine if the root term is a TERM or EVENT
        root_node = self.graph.node[self.root_term]
        if root_node['category'] == 'ONT::TERM':
            self.term_to_ekb(self.root_term)
        else:
            self.generic_event_to_ekb(self.root_term)

    def to_string(self):
        ekb_str = etree.tounicode(self.ekb, pretty_print=True)
        ekb_str = '<?xml version="1.0"?>' + ekb_str
        return ekb_str

    def get_agent(self):
        ekb_str = self.to_string()
        tp = TripsProcessor(ekb_str)
        agent = tp._get_agent_by_id(self.root_term, None)
        return agent

    def event_to_ekb(self, event_node):
        node = self.graph.node[event_node]
        if node['type'].upper() == 'ONT::ATTACH':
            self.binding_to_ekb(event_node)
        else:
            self.generic_event_to_ekb(event_node)

    def binding_to_ekb(self, event_node):
        event = etree.Element('EVENT', id=event_node)
        type = etree.Element('type')
        event.append(type)
        type.text = 'ONT::BIND'
        ekb_args = {'affected': ('arg1', ':AGENT'),
                    'affected1': ('arg2', ':AFFECTED'),
                    'agent': ('arg2', ':AFFECTED')}
        for kqml_link, (tag_name, tag_type) in ekb_args.items():
            arg = self.graph.get_matching_node(event_node, link=kqml_link)
            if arg is None:
                continue
            if arg not in self.components:
                self.term_to_ekb(arg)
            arg_tag = etree.Element(tag_name, id=arg, type=tag_type)
            event.append(arg_tag)
        self.components.append(event_node)
        self.ekb.append(event)

    def generic_event_to_ekb(self, event_node):
        node = self.graph.node[event_node]
        event = etree.Element('EVENT', id=event_node)
        type = etree.Element('type')
        type.text = node['type']
        event.append(type)
        arg_counter = 1
        possible_event_args = ['affected', 'affected1', 'agent',
                               'affected-result']
        for event_arg in possible_event_args:
            arg_node = self.graph.get_matching_node(event_node, link=event_arg)
            if arg_node:
                tag_name = 'arg%d' % arg_counter
                tag_type = ':%s' % event_arg.upper()
                arg_tag = etree.Element(tag_name, id=arg_node, role=tag_type)
                event.append(arg_tag)
                arg_counter += 1
                if arg_node not in self.components:
                    self.term_to_ekb(arg_node)
        # Extract any sites attached to the event
        site_node = self.graph.get_matching_node(event_node, link='site')
        if site_node:
            site_tag = etree.Element('site', id=site_node)
            event.append(site_tag)
            site_term = self.get_site_term(site_node)
            self.ekb.append(site_term)

        self.components.append(event_node)
        self.ekb.append(event)

    def get_site_term(self, site_node):
        site_term = etree.Element('TERM', id=site_node)
        type_elem = etree.Element('type')
        site_term.append(type_elem)
        type_elem.text = 'ONT::MOLECULAR-SITE'
        # Now we need to look for the site
        site_dbname = self.graph.get_matching_node_value(site_node, link='dbname')
        site_name = self.graph.get_matching_node_value(site_node, link='site-name')
        site_code = self.graph.get_matching_node_value(site_node, link='site-code')
        if site_dbname:
            if site_dbname.lower().startswith('serine'):
                code = 'S'
            elif site_dbname.lower().startswith('threonine'):
                code = 'T'
            elif site_dbname.lower().startswith('tyrosine'):
                code = 'Y'
        elif site_code:
            label = site_name
            code = site_code
        else:
            raise ValueError('No site code found')
        site_pos = self.graph.get_matching_node_value(site_node, link='site-pos')
        name_elem = etree.Element('name')
        name_elem.text = label
        site_term.append(name_elem)
        features_tag = etree.Element('features')
        site_tag = etree.Element('site')
        site_name_tag = etree.Element('name')
        site_name_tag.text = label
        site_code_tag = etree.Element('code')
        site_code_tag.text = code
        site_pos_tag = etree.Element('pos')
        site_pos_tag.text = site_pos
        site_tag.append(site_name_tag)
        site_tag.append(site_code_tag)
        site_tag.append(site_pos_tag)
        features_tag.append(site_tag)
        site_term.append(features_tag)
        return site_term

    def get_term_name(self, term_id):
        name_node = self.graph.get_matching_node(term_id, link='name')
        if not name_node:
            name_node = self.graph.get_matching_node(term_id, link='W')
        name_val = self.graph.node[name_node]['label']
        if name_val.startswith('W::'):
            name_val = name_val[3:]
        return name_val

    def term_to_ekb(self, term_id):
        node = self.graph.node[term_id]

        term = etree.Element('TERM', id=term_id)

        # Set the type of the TERM
        type = etree.Element('type')
        type.text = node['type']
        term.append(type)

        # Find the name of the TERM and get the value with W:: stripped
        if node['type'].upper() == 'ONT::SIGNALING-PATHWAY':
            path_subject_id = self.graph.get_matching_node(term_id,
                                                           link='assoc-with')
            path_subject_name = self.get_term_name(path_subject_id)
            name_val = path_subject_name.upper() + '-SIGNALING-PATHWAY'

            # This is a LITTLE bit hacky.
            term_id = path_subject_id
        else:
            name_val = self.get_term_name(term_id)
        name = etree.Element('name')
        name.text = name_val
        term.append(name)

        # Now deal with DRUM content
        drum_node = self.graph.get_matching_node(term_id, link='drum')
        if drum_node:
            drum_kqml = KQMLList.from_string(self.graph.node[drum_node]['kqml'])
            drum_terms = etree.Element('drum-terms')
            for drum_term in drum_kqml[0][1:]:
                dt = drum_term_to_ekb(drum_term)
                if dt is not None:
                    drum_terms.append(dt)
            term.append(drum_terms)

        # Deal next with modifier events
        mod = self.graph.get_matching_node(term_id, link='mod')
        if mod:
            if mod not in self.components:
                self.event_to_ekb(mod)
            features = etree.Element('features')
            event = self.graph.node[mod]
            if event['type'].upper() == 'ONT::ACTIVE':
                active = etree.Element('active')
                active.text = 'TRUE'
                features.append(active)
            else:
                inevent = etree.Element('inevent', id=mod)
                features.append(inevent)
            term.append(features)

        self.ekb.append(term)


def drum_term_to_ekb(drum_term):
    def get_dbid(drum_id):
        term_id_ns, term_id_id = drum_id.split('::')
        term_id_id = term_id_id.strip('|')
        dbid = '%s:%s' % (term_id_ns, term_id_id)
        return dbid
    # Get dbid attribute
    term_id = drum_term.gets('id')
    if term_id is None:
        return None
    dbid = get_dbid(term_id)

    # Get the first element of matches and its content
    match = drum_term.get('matches')[0]
    match_score = match.gets('score')
    match_matched = match.gets('matched')
    # NOTE: these two below don't seem to be added to the EKB
    # match_status = match.gets('status')
    # match_exact = int(match.gets('exact'))

    # Get the xrefs
    dbxrefs_entry = drum_term.get('dbxrefs')
    if dbxrefs_entry:
        dbxrefs = [get_dbid(xr.string_value())
                   for xr in dbxrefs_entry]
    else:
        dbxrefs = []

    # Get ont type
    ont_type = drum_term.get('ont-types')[0].string_value()

    # Now that we have all the pieces we can assemble
    # the XML structure
    dt = etree.Element('drum-term', dbid=dbid, name=match_matched)
    dt.attrib['match-score'] = match_score
    dt.attrib['matched-name'] = match_matched
    types = etree.Element('types')
    type = etree.Element('type')
    type.text = ont_type
    types.append(type)
    if dbxrefs:
        xrefs = etree.Element('xrefs')
        for dbxref in dbxrefs:
            xref = etree.Element('xref', dbid=dbxref)
            xrefs.append(xref)
        dt.append(xrefs)
    return dt


def agent_from_term(graph, term_node):
    ekb = EKB(graph, term_node)
    return ekb.get_agent()
