from ltl_nodes import build_tree

class ModelChecker(object):
    def __init__(self, formula_str, states=None):
        self.formula_str = formula_str
        self.roots = []
        self.time = 0

        # Downsample here for speed
        states = states[::5]

        root = build_tree(self.formula_str)
        self.roots.append(root)

        if states is not None:
            for t, s in enumerate(states):
                tf = self.update(s, (t == (len(states)-1)))
                if tf is not None:
                    break
            self.truth = tf
        else:
            self.truth = None

    def update(self, x, is_last=False):
        self.roots[self.time].update(x, is_last)
        tf = self.roots[0].eval_node()
        if tf is None:
            self.roots.append(self.roots[self.time].duplicate())
            self.roots[self.time].link(self.roots[self.time+1])
        self.time += 1
        self.truth = tf
        return self.truth

def transient_formula(var_id):
    fstr = 'F[%s,1,1] & FG([%s,0,0])' % (var_id, var_id)
    return fstr

def sustained_formula(var_id):
    fstr = 'FG[%s,1,1]' % var_id
    return fstr

def noact_formula(var_id):
    fstr = 'G[%s,0,0]' % var_id
    return fstr

def always_formula(var_id, value):
    fstr = 'G[%s,%d,%d]' % (var_id, value, value)
    return fstr

def eventual_formula(var_id, value):
    fstr = 'FG[%s,%d,%d]' % (var_id, value, value)
    return fstr

def sometime_formula(var_id, value):
    fstr = 'F[%s,%d,%d]' % (var_id, value, value)
    return fstr
