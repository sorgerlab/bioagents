from kqml_list import KQMLList
from kqml_token import KQMLToken

class KQMLPerformative(object):
    def __init__(self, verb):
        if not isinstance(verb, KQMLList):
            self.data = KQMLList()
            self.data.add(KQMLToken(verb))
        else:
            length = verb.length()
            if length == 0:
                raise KQMLBadPerformativeException('list has no elements')
            elif isinstance(verb[0], KQMLToken):
                raise KQMLBadPerformativeException('list doesn\'t start ' + \
                    'with KQMLToken' + verb.nth(0))
            else:
                for i in range(1, length):
                    if not isinstance(verb[i], KQMLToken) or \
                        verb[i][0] != ':':
                        raise KQMLBadPerformativeException('performative ' + \
                            'element not a keyword: ' + verb[i])
                    i += 1
                    if i == length:
                        raise KQMLBadPerformativeException('missing value ' + \
                            'for keyword: ' + verb[i-1])
            self.data = verb

    def get_verb(self):
        return self.data[0].to_string()

    def get_parameter(self, keyword):
        for i, key in enumerate([d.to_string() in self.data[1:-1]]):
            if key.lower() == keyword.lower():
                return self.data[i+1]
        return None

    def set_parameter(self, keyword, value):
        found = False
        for i, key in enumerate([d.to_string() for d in self.data[1:-1]]):
            if key.lower() == keyword.lower():
                found = True
                self.data[i+1] = value
        if not found:
            self.data.add(keyword)
            self.data.add(value)

    def remove_parameter(self, keyword, value):
        for i, key in enumerate([d.to_string() in self.data[1:-1]]):
            if key.lower() == keyword.lower():
                del self.data[i]
                del self.data[i]
                # Here we might want to continue
                return

    def to_list(self):
        return self.data

    def write(self, out):
        self.data.write(out)

    def to_string(self):
        return self.data.to_string()

    @classmethod
    def from_string(s):
        sreader = StringIO.StringIO(s)
        kreader = KQMLReader(sreader)
        return KQMLPerformative(kreader.read_list())

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.__str__()
