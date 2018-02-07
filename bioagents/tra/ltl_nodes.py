import re
from copy import deepcopy

def is_balanced(s, lc='(', rc=')'):
    is_bal = 0
    for i in range(len(s))[1:]:
        is_bal += (s[i] == lc) - (s[i-1] == rc)
    return is_bal

def build_tree(formula_str, time_lim=None):
    root = None
    fstr = formula_str.strip()

    str_r = fstr
    str_l = None
    while True:
        parts = re.split('\|', fstr)
        if len(parts) == 1:
            break
        str_l, str_r = parts[0], '|'.join(parts[1:])
        if (is_balanced(str_l) == 0):
            child1 = build_tree(str_l, time_lim)
            child2 = build_tree(str_r, time_lim)
            root = OrNode(time_lim, child1, child2)
            return root

    str_r = fstr
    str_l = None
    while True:
        parts = re.split('&', fstr)
        if len(parts) == 1:
            break
        str_l, str_r = parts[0], '&'.join(parts[1:])
        if (is_balanced(str_l) == 0):
            child1 = build_tree(str_l, time_lim)
            child2 = build_tree(str_r, time_lim)
            root = AndNode(time_lim, child1, child2)
            return root

    first_ch = fstr[0]
    last_ch = fstr[-1]
    if first_ch == '!':
        child1 = build_tree(fstr[1:], time_lim)
        root = NotNode(time_lim, child1)
    elif first_ch == 'F':
        child1 = build_tree(fstr[1:], time_lim)
        root = FNode(time_lim, child1)
    elif first_ch == 'G':
        child1 = build_tree(fstr[1:], time_lim)
        root = GNode(time_lim, child1)
    elif first_ch == '[':
        if last_ch == ']':
            var_id, lb, ub = fstr[1:-1].split(',')
            lb = int(lb)
            ub = int(ub)
            root = AtomicNode(var_id, lb, ub)
    elif first_ch == '(':
        if last_ch == ')':
            root = build_tree(fstr[1:-1], time_lim)
    if root is not None:
        return root


class Node(object):
    def __init__(self, time_lim=None, child1=None, child2=None):
        self.time = 0
        self.time_lim = time_lim
        self.child1 = child1
        self.child2 = child2
        self.next_node = None
        self.previous_node = None
        self.truth = None

    def eval_node(self):
        return self.truth

    def erase_truth(self):
        self.truth = None
        if self.child1 is not None:
            self.child1.erase_truth()
        if self.child2 is not None:
            self.child2.erase_truth()

    def duplicate(self):
        self_copy = deepcopy(self)
        self_copy.erase_truth()
        return self_copy

    def link(self, other):
        if self.child1 is not None:
            self.child1.link(other.child1)
        if self.child2 is not None:
            self.child2.link(other.child2)
        self.next_node = other
        self.next_node.time = self.time + 1
        self.next_node.previous_node = self

    def update(self, x, is_last=False):
        self.is_last = is_last
        if self.child1 is not None:
            self.child1.update(x, is_last)
        if self.child2 is not None:
            self.child2.update(x, is_last)

    def __repr__(self):
        s = self.__class__.__name__
        if self.child1 is not None:
            s += '(' + self.child1.__repr__()
            if self.child2 is not None:
                s += ', ' + self.child2.__repr__() + ')'
            else:
                s += ')'
        return s

class FNode(Node):
    def eval_node(self):
        if self.truth is not None:
            return self.truth
        tf = self.child1.eval_node()
        if self.is_last or (self.time_lim is not None and
                            (self.time == self.time_lim)):
            self.truth = tf
        else:
            if tf is True:
                self.truth = True
            else:
                if self.next_node is None:
                    self.truth = None
                else:
                    tfx = self.next_node.eval_node()
                    self.truth = tfx
        return self.truth

class GNode(Node):
    def eval_node(self):
        if self.truth is not None:
            return self.truth
        tf = self.child1.eval_node()
        if self.is_last or (self.time_lim is not None and
                            (self.time == self.time_lim)):
            self.truth = tf
        else:
            if tf is False:
                self.truth = False
            else:
                if self.next_node is None:
                    self.truth = None
                else:
                    tfx = self.next_node.eval_node()
                    self.truth = tfx
        return self.truth

class AndNode(Node):
    def eval_node(self):
        if self.truth is not None:
            return self.truth
        tf1 = self.child1.eval_node()
        if tf1 is False:
            self.truth = False
        else:
            tf2 = self.child2.eval_node()
            if tf2 is False:
                self.truth = False
            elif tf2 is True and tf1 is True:
                self.truth = True
            else:
                self.truth = None
        return self.truth

class OrNode(Node):
    def eval_node(self):
        if self.truth is not None:
            return self.truth
        tf1 = self.child1.eval_node()
        if tf1 is True:
            self.truth = True
        else:
            tf2 = self.child2.eval_node()
            if tf2 is True:
                self.truth = True
            elif tf2 is False and tf1 is False:
                self.truth = False
            else:
                self.truth = None
        return self.truth


class NotNode(Node):
    def eval_node(self):
        # If thruth is already known
        if self.truth is not None:
            return self.truth
        # Evaluate child
        tf = self.child1.eval_node()
        # If child's truth is now known
        if tf is not None:
            self.truth = (not tf)
            return self.truth
        # If child's truth is still not known return None
        else:
            return None

class AtomicNode(Node):
    def __init__(self, var_id, lb=None, ub=None):
        super(AtomicNode, self).__init__()
        self.var_id = var_id
        self.lb = lb
        self.ub = ub

    def update(self, x, is_last=False):
        if (self.lb is None or x[self.var_id] >= self.lb) and\
            (self.ub is None or x[self.var_id] <= self.ub):
            self.truth = True
        else:
            self.truth = False
        self.is_last = is_last

    def eval_node(self):
        return self.truth

    def __repr__(self):
        s = '[%s,%s,%s]=%s' % (self.var_id, self.lb, self.ub, self.truth)
        return s
