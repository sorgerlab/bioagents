""" Web api client for the kappa programming language
"""

import urllib, urllib2
import json

class RuntimeError(Exception):
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
                error_details = json.loads(e.read())
                raise RuntimeError(error_details)
            else:
                raise e

    def start(self,code):
        method = "POST"
        handler = urllib2.HTTPHandler()
        opener = urllib2.build_opener(handler)
        parse_url = "{0}/process".format(self.url)
        print parse_url
        request = urllib2.Request(parse_url, data=code)
        request.get_method = lambda: method
        try:
            connection = opener.open(request)
        except urllib2.HTTPError,e:
            connection = e
            
        if e.code == 200:
            text = connection.read()
            return json.loads(text)
        elif e.code == 400:
            text = connection.read()
            error_details = json.loads(text)
            raise RuntimeError(error_details)
        else:
            raise e

if __name__ == "__main__":
    print KappaRuntime("http://localhost:8080").start("%var: 'one' 1")
