""" Web api client for the kappa programming language
"""

import urllib, urllib2
import json
import subprocess


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
        try:
            version_url = "{0}/version".format(self.url)
            response = urllib2.urlopen(version_url)
            text = response.read()
            return json.loads(text)
        except urllib2.URLError as e:
            raise RuntimeError(e.reason)

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
        except urllib2.URLError as e:
            RuntimeError(e.reason)

    """ parse code throw an exception if the parse
        fails.
    """
    def start(self,parameter):
        if not 'max_time' in parameter:
            parameter['max_time'] = None
        if not 'max_events' in parameter:
            parameter['max_events'] = None
        code = json.dumps(parameter)
        method = "POST"
        handler = urllib2.HTTPHandler()
        opener = urllib2.build_opener(handler)
        parse_url = "{0}/process".format(self.url)
        request = urllib2.Request(parse_url, data=code)
        request.get_method = lambda: method
        try:
            connection = opener.open(request)
        except urllib2.HTTPError,e:
            connection = e
        except urllib2.URLError as e:
            raise RuntimeError(e.reason)

        if connection.code == 200:
            text = connection.read()
            return int(json.loads(text))
        elif connection.code == 400:
            text = connection.read()
            error_details = json.loads(text)
            raise RuntimeError(error_details)
        else:
            raise e

    """ stop running process
    """
    def stop(self,token):
        method = "DELETE"
        handler = urllib2.HTTPHandler()
        opener = urllib2.build_opener(handler)
        parse_url = "{0}/process/{1}".format(self.url,token)
        request = urllib2.Request(parse_url)
        request.get_method = lambda: method
        try:
            connection = opener.open(request)
        except urllib2.HTTPError,e:
            connection = e
        except urllib2.URLError as e:
            raise RuntimeError(e.reason)

        if connection.code == 200:
            text = connection.read()
            return None
        elif connection.code == 400:
            text = connection.read()
            error_details = json.loads(text)
            raise RuntimeError(error_details)
        else:
            raise e

    """ status of running process
    """
    def status(self,token):
        try:
            version_url = "{0}/process/{1}".format(self.url,token)
            response = urllib2.urlopen(version_url)
            text = response.read()
            return json.loads(text)
        except urllib2.HTTPError as e:
            if e.code == 400:
                error_details = json.loads(e.read())
                raise RuntimeError(error_details)
            else:
                raise e
        except urllib2.URLError as e:
            RuntimeError(e.reason)


    """ shutdown server
    """
    def shutdown(self,key):
        method = "POST"
        handler = urllib2.HTTPHandler()
        opener = urllib2.build_opener(handler)
        parse_url = "{0}/shutdown".format(self.url)
        request = urllib2.Request(parse_url, data=key)
        request.get_method = lambda: method
        try:
            connection = opener.open(request)
        except urllib2.HTTPError,e:
            connection = e
        except urllib2.URLError as e:
            raise RuntimeError(e.reason)
        if connection.code == 200:
            text = connection.read()
            return text
        elif connection.code == 400:
            text = connection.read()
            raise RuntimeError(text)
        elif connection.code == 401:
            text = connection.read()
            raise RuntimeError(text)
        else:
            raise e

from jnius import autoclass, cast
from TripsModule import trips_module
from kappa_client import KappaRuntime, RuntimeError
from time import sleep

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')


if __name__ == "__main__":
    with open("../abc-pert.ka") as f:
        try:
            subprocess.Popen('../WebSim.native --shutdown-key 6666 --port 6666'.split())
            sleep(1)
            data = f.read()
            runtime = KappaRuntime("http://localhost:6666")
            token = runtime.start({ 'code': data
                                  , 'nb_plot': 10
                                  , 'max_events' : 10000 })
            sleep(10)
            status = runtime.status(token)
            print status
            print render_status(status).toString()
            print runtime.shutdown('6666')
        except RuntimeError as e:
            print e.errors
