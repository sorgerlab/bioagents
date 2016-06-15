import StringIO

class KQMLToken(object):
    def __init__(self, s=None):
        if s is None:
            self.data = ''
        else:
            self.data = s

    def length(self):
        return len(self.data)

    def char_at(self, n):
        return self.data[n]

    def equals(self, other):
        return self.__eq__(self, other)

    def equals_ignore_case(self, s):
        if isinstance(s, KQMLToken):
            return (self.data.lower() == s.lower())

    def write(self, out):
        out.write(self.data)

    def to_string(self):
        out = StringIO.StringIO()
        try:
            self.write(out)
        except Exception:
            pass
        return out.getvalue()

    def string_value(self):
        return self.__str__()

    def get_package(self):
        results = self.parse_package()
        return results[0]

    def has_package(self):
        pkg = self.get_package()
        return (pkg is not None)

    def get_name(self):
        results = self.parse_package()
        return results[1]

    KEYWORD_PACKAGE_NAME = 'KEYWORD'

    def is_keyword(self):
        package_name = self.get_package()
        return (KEYWORD_PACKAGE_NAME.lower() == package_name)

    def parse_package(self):
        package_name = None
        bare_name = ''
        quoted = False
        chars = iter([c for c in self.data])
        i = 0
        while i <= len(chars):
            c = chars[i]
            if c == '|':
                quoted = not quoted
                bare_name += c
            elif (not quoted) and (c == ':'):
                if bare_name == '':
                    package_name = KEYWORD_PACKAGE_NAME
                else:
                    package_name = bare_name
                    bare_name = ''
                if i == len(chars)-1:
                    raise Exception('token ends in a colon: ' + self.data)
                i += 1
                c = chars[i]
                if c == ':':
                    if i == len(chars)-1:
                        raise Exception('token ends in a colon: ' + self.data)
                else:
                    i -= 1
            else:
                bare_name += c
        if quoted:
            raise Exception('no closing bar: ' + self.data)

        return (package_name, bare_name)

    def __getitem__(self, *args):
        return self.data.__getitem__(*args)

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        s = self.to_string()
        s = s.replace('\n', '\\n')
        return s

    def __eq__(self, other):
        if not isinstance(other, KQMLToken):
            return False
        elif self.data == other.data:
            return True
        else:
            return False
