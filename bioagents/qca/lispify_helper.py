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
                #print "key: " + key
                #print L[key]
                tmp_key = str(key)
                if not tmp_key.isalnum():
                    tmp_key = '"%s"' % tmp_key
                if key == "INDRA statement":
                    s += [":{0} {1}".format(tmp_key, self.lispify(L[key], True))]
                else:
                    s += [":{0} {1}".format(tmp_key, self.lispify(L[key], False))]
            return '(' + ' '.join(s) + ')'
        elif isinstance(L, unicode):
            if indra_statement:
                return '"%s"' % str(L)
            else:
                return str(L)
        else:
            return L
