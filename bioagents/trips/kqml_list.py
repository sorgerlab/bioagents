import StringIO
from kqml_token import KQMLToken
import kqml_reader

class KQMLList(object):
    def __init__(self, objects=None):
        if objects is None:
            self.data = []
        else:
            for o in objects:
                self.data.append(o)

    def __str__(self):
        return '(' + ' '.join([d.__str__() for d in self.data]) + ')'

    def __repr__(self):
        return '(' + ' '.join([d.__repr__() for d in self.data]) + ')'

    def __getitem__(self, *args):
        return self.data.__getitem__(*args)

    def __len__(self):
        return len(self.data)

    #TODO: implement adding by index, KQMLList line 246
    def add(self, obj):
        if isinstance(obj, basestring):
            self.data.append(KQMLToken(obj))
        else:
            self.data.append(obj)

    # TODO: check if java indexOf return values are consistent
    def index_of_string(self, s):
        try:
            idx = self.data.index(s)
            return idx
        except ValueError:
            return -1

    def push(self, obj):
        self.data.insert(0, obj)

    def insert_at(self, obj, index):
        self.data.insert(index, obj)

    def remove_at(self, index):
        del self.data[index]

    def nth(self, n):
        return self.data[n]

    def length(self):
        return len(self.data)

    def get_keyword_arg(self, keyword):
        for i, s in enumerate(self.data):
            if s.to_string().upper() == keyword.upper():
                if i < len(self.data)-1:
                    return self.data[i+1]
                else:
                    return None
        return None

    def remove_keyword_arg(self, keyword):
        raise Exception('Not implemented')

    def write(self, out):
        full_str = '(' + ' '.join([str(s) for s in self.data]) + ')'
        out.write(full_str)

    def to_string(self):
        out = StringIO.StringIO()
        self.write(out)
        return out.getvalue()

    @classmethod
    def from_string(cls, s):
        sreader = StringIO.StringIO(s)
        kreader = kqml_reader.KQMLReader(sreader)
        return kreader.read_list()

    def sublist(self, from_idx, to_idx):
        return KQMLList(self.data[from_idx:to_idx])

    def remove(self, obj):
        self.data.remove(obj)

    def index_of(self, obj):
        if isinstance(obj, basestring):
            return self.index_of_string(obj)
        else:
            try:
                idx = self.data.index(obj)
                return idx
            except ValueError:
                return -1

    def index_of_ignore_cae(self, keyword):
        for i, s in enumerate(self.data):
            if s.lower() == keyword.lower():
                return i
        return -1

    #TODO: didn't implement all the functions here
