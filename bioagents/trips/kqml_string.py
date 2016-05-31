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
    
    # TODO: make sure that the double quotes are printed correctly
    def write(self, out):
        data_str = out.write(self.data)

    def to_string(self):
        out = StringIO.StringIO()
        self.write(out)

    def string_value(self):
        return self.data
