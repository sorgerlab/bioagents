import StringIO

class KQMLString(object):
    def __init__(self, data=None):
        if data is None:
            self.data = ''
        else:
            self.data = data

    def length(self):
        return len(self.data)

    def char_at(self, n):
        return self.data[n]

    def equals(self, obj):
        if not isinstance(obj, KQMLString):
            return False
        else:
            return obj.data == self.data

    def write(self, out):
        out.write('"')
        for ch in self.data:
            #if ch == '"' or ch == '\\':
            if ch == '"':
                out.write('\\')
            out.write(ch)
        out.write('"')

    def to_string(self):
        out = StringIO.StringIO()
        self.write(out)
        return out.getvalue()

    def string_value(self):
        return self.data

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        s = self.__str__()
        s = s.replace('\n', '\\n')
        return s
