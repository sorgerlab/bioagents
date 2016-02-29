""" Web api client for the kappa programming language
"""

import urllib, urllib2
import json

class ParseError(Exception):
    def __init__(self, errors):
        self.errors = errors

class KappaRuntime(object):
    """ Create a client by supplying a web endpoint
    """
    def __init__(self, endpoint):
        self.url = "{0}/v1".format(endpoint)

    """ get version of environment this should provide
        a quick status check for the endpoint as the
        URL is already versioned.
    """
    def version(self):
        version_url = "{0}/version".format(self.url)
        response = urllib2.urlopen(version_url)
        text = response.read()
        return json.loads(text)

    """ parse code throw an exception if the parse
        fails.
    """
    def parse(self,code):
        query_args = { 'code':code }
        encoded_args = urllib.urlencode(query_args)
        parse_url = "{0}/parse?{1}".format(self.url,encoded_args)
        try:
            response = urllib2.urlopen(parse_url)
            text = response.read()
            return json.loads(text)
        except urllib2.HTTPError as e:
            if e.code == 400:
                raise ParseError(json.loads(e.read()))
            else:
                raise e


if __name__ == "__main__":
    print KappaRuntime("http://localhost:8080").version()
    print KappaRuntime("http://localhost:8080").parse("a")
