import StringIO
import kqml_reader
import kqml_list
from kqml_token import KQMLToken
from kqml_exceptions import KQMLBadPerformativeException

class KQMLPerformative(object):
    def __init__(self, verb):
        if not isinstance(verb, kqml_list.KQMLList):
            self.data = kqml_list.KQMLList()
            self.data.add(KQMLToken(verb))
        else:
            length = verb.length()
            if length == 0:
                raise KQMLBadPerformativeException('list has no elements')
            elif not isinstance(verb[0], KQMLToken):
                raise KQMLBadPerformativeException('list doesn\'t start ' + \
                    'with KQMLToken: ' + str(verb.nth(0)))
            else:
                i = 1
                while i < length:
                    if not isinstance(verb[i], KQMLToken) or \
                        verb[i][0] != ':':
                        raise KQMLBadPerformativeException('performative ' + \
                            'element not a keyword: ' + verb[i])
                    # Increment counter after keyword
                    i += 1
                    if i == length:
                        raise KQMLBadPerformativeException('missing value ' + \
                            'for keyword: ' + verb[i-1])
                    i += 1
            self.data = verb

    def get_verb(self):
        return self.data[0].to_string()

    def get_parameter(self, keyword):
        for i, key in enumerate([d.to_string() for d in self.data[:-1]]):
            if key.lower() == keyword.lower():
                return self.data[i+1]
        return None

    def set_parameter(self, keyword, value):
        found = False
        for i, key in enumerate([d.to_string() for d in self.data[:-1]]):
            if key.lower() == keyword.lower():
                found = True
                self.data[i+1] = value
        if not found:
            self.data.add(keyword)
            self.data.add(value)

    def remove_parameter(self, keyword, value):
        for i, key in enumerate([d.to_string() for d in self.data[:-1]]):
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
    def from_string(cls, s):
        sreader = StringIO.StringIO(s)
        kreader = kqml_reader.KQMLReader(sreader)
        return cls(kreader.read_list())

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.data.__repr__()
