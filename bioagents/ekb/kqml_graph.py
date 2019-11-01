"""Turn KQML into graphs"""
import networkx
from kqml import KQMLList, KQMLToken, KQMLString


class KQMLGraph(networkx.DiGraph):
    """Represents a KQML graph with an underlying networkx structure.

    Since it inherits from networkx.DiGraph, the KQML graph can be
    manipulated using standard networkx methods. On top of the underlying
    networkx structure this class makes available a number of pattern queries
    on the graph. There are two main types of pattern queries: `get`
    queries and `assert` queries. With `get` queries, if a given pattern
    matches, a result is returned, otherwise None is returned. It is the
    responsibility of the caller to handle None results. In contrast,
    `assert` queries raise an exception if the given pattern doesn't match.
    This relieves the caller of having to check each query result independently,
    and consolidate exception handling into a single try/except block to
    determine if a patter has been matched.

    Parameters
    ----------
    kqml : str of KQMLList or a KQMLList
        A string representing a KQML message that is to be represented
        as a graph. Should be a list of terms.
    """
    def __init__(self, kqml):
        super().__init__()
        if isinstance(kqml, KQMLList):
            self.from_kqml_list(kqml)
        else:
            self.from_kqml_str(kqml)

    def from_kqml_str(self, kqml_str):
        """Create a networkx graph from a KQML string

        Parameters
        ----------
        kqml_str : str
            A string representing a KQML message that is to be represented
            as a graph.
        """
        # Deserialize the KQML string
        kl = KQMLList.from_string(kqml_str)
        return self.from_kqml_list(kl)

    def from_kqml_list(self, kqml_list):
        # We ignore edges that talk about offsets in text
        drop_edges = ['RULE', 'SPEC', 'FORCE', '-NOOP', '-ADD-SPEC']
        # Look at the elements in the list and convert into nodes
        for elem in kqml_list:
            # Get the category of the element (TERM, EVENT, etc.)
            elem_category = elem[0]
            # Get the ID of the element
            elem_id = elem[1].string_value()
            # We use the V IDs without the ONT prefix
            if elem_id.startswith('ONT::V'):
                elem_id = elem_id[5:]

            # Let's get the instance-of as the type
            elem_type = elem.gets('INSTANCE-OF')

            # We now add the node with its ID, type and label
            self.add_node(elem_id, type=elem_type,
                          label='%s (%s)' % (elem_type, elem_id),
                          category=elem_category)

            # The rest of the entry is always a list of keyword args like
            # :ARG VALUE which we iterate over
            for idx, (key, val) in enumerate(zip(elem[4::2], elem[5::2])):
                # Drop the : from the beginning of the argument
                key = key.string_value()[1:]
                if key in drop_edges:
                    continue
                # Now there are a few possibilities in terms of what the value
                # can be
                # If it's a token or string, we turn it into a Python str
                if isinstance(val, (KQMLToken, KQMLString)):
                    val = str(val)
                    # If it's a V node, we strip ONT and add an edge
                    if val.startswith('ONT::V'):
                        self.add_edge(elem_id, val[5:], label=key)
                    # Otherwise it's just a regular node that we add
                    else:
                        node_idx = '%s%s' % (elem_id, idx)
                        self.add_node(node_idx, label=val)
                        self.add_edge(elem_id, node_idx, label=key)
                # If it's a list then
                elif isinstance(val, KQMLList):
                    if key.upper() == 'DRUM':
                        node_idx = '%s%s' % (elem_id, idx)
                        self.add_node(node_idx, label='DRUM', kqml=str(val))
                        self.add_edge(elem_id, node_idx, label=key)
                    # This is one of those special triplets like
                    # :MODALITY (:* ONT::DO W::DO), we take the second
                    # element
                    elif val.head() == ':*':
                        node_idx = '%s%s' % (elem_id, idx)
                        node_val = str(val[1])
                        self.add_node(node_idx, label=node_val)
                        self.add_edge(elem_id, node_idx, label=key)
                    # This is the case when there is a sequence of symbols
                    # being referred to, typically with an AND operator
                    elif key.upper() in ['SEQUENCE', 'M-SEQUENCE']:
                        for counter, seq_elem in enumerate(val):
                            assert str(seq_elem).startswith('ONT::V')
                            label = key.lower() + '%s' % ('' if counter == 0
                                                          else counter)
                            self.add_edge(elem_id, seq_elem[5:], label=label)
                    else:
                        raise ValueError('Unexpected KQMLList encountered')
                else:
                    raise ValueError('Unexpected value %s encountered' %
                                     type(val))

    def draw(self, fname):
        """Draw a graph and save into a given file.

        Parameters
        -----------
        fname : str
            The name of the file to save the graph into.
        """
        ag = networkx.nx_agraph.to_agraph(self)
        # Add some visual styles to the graph
        ag.node_attr['shape'] = 'plaintext'
        ag.draw(fname, prog='dot')

    def get_matching_node(self, node, link=None, target_type=None):
        """Return first matching node or None if there is no match.

        Parameters
        ----------
        node : str
            The identifier of the node to start from
        link : Optional[str]
            The type of edge going out from the given node. If not given,
            the type of edge is not constrained.
        target_type : Optional[str]
            The type of node the edge is pointing to. If not given, the
            type of node is not constrained.

        Returns
        -------
        nodes : str
            A matching node identifier.
        """
        nodes = self.get_matching_nodes(node, link, target_type)
        if not nodes:
            return None
        return nodes[0]

    def get_matching_node_value(self, node, link=None, target_type=None):
        node_id = self.get_matching_node(node, link, target_type)
        if node_id is None:
            return None
        node = self.nodes[node_id]
        label = node['label']
        if label.startswith('"'):
            label = label[1:-1]
        return label

    def get_matching_nodes(self, node, link=None, target_type=None):
        """Return all matching nodes or empty list if there is no match.

        Parameters
        ----------
        node : str
            The identifier of the node to start from
        link : Optional[str]
            The type of edge going out from the given node. If not given,
            the type of edge is not constrained.
        target_type : Optional[str]
            The type of node the edge is pointing to. If not given, the
            type of node is not constrained.

        Returns
        -------
        nodes : list[str]
            A list of matching node identifiers.
        """
        # Handle OR clause of links
        if isinstance(link, (tuple, list)):
            links_to_match = [l.lower() for l in link]
        elif link:
            links_to_match = [link.lower()]

        # Handle OR clause of target types
        if isinstance(target_type, (tuple, list)):
            targets_to_match = [t.lower() for t in target_type]
        elif target_type:
            targets_to_match = [target_type.lower()]

        edges = self.out_edges(node, data=True)
        # Filter for edges
        matched_edges = edges if not link else \
            [e for e in edges if e[2]['label'].lower() in links_to_match]
        # Filter for nodes
        matched_nodes = [e[1] for e in matched_edges if
                         (not target_type or
                          ('type' in self.nodes[e[1]] and
                           (self.nodes[e[1]]['type'].lower() in
                            targets_to_match)))]
        return matched_nodes
