__author__ = 'aarongary'

class Lispify():
    def __init__(self, obj):
        if(obj is None):
            raise ValueError("Please provide an object")

        self.obj = obj

    def to_lisp(self):
        if type(self.obj) is unicode:
            return self.lispify(str(self.obj))
        else:
            return self.lispify(self.obj)

    def lispify(self, L, indra_statement=False):
        "Convert a Python object L to a lisp representation."
        if (isinstance(L, str)
            or isinstance(L, float)
            or isinstance(L, int)):

            if indra_statement:
                return '"%s"' % L
            elif not L.isalnum():
                return '"%s"' % L
            else:
                return L

        elif (isinstance(L, list)
              or isinstance(L, tuple)):
            s = []
            for element in L:
                s += [self.lispify(element)]
            return '(' + ' '.join(s) + ')'
        elif isinstance(L, dict):
            s = []
            for key in L:
                tmp_key = str(key)
                if " " in tmp_key:
                    tmp_key = "_".join(tmp_key.split())
                if key == "INDRA statement":  # Indra statements need to be quoted
                    s += [":{0} {1}".format("INDRA_statement", self.lispify(L[key], True))]
                else:
                    s += [":{0} {1}".format(tmp_key, self.lispify(L[key], False))]
            return '(' + ' '.join(s) + ')'
        elif isinstance(L, unicode):
            if indra_statement or not L.isalnum():
                print L
                return '"%s"' % str(L)
            else:
                return str(L)
        else:
            return L
