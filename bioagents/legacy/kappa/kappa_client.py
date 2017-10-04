"""Web API client for a Kappa simulator."""

import urllib2
import json
import requests
from time import sleep


class KappaRuntimeError(Exception):
    def __init__(self, errors):
        self.errors = errors


kappa_default = 'http://api.executableknowledge.org/kappa/v2/projects/default'
kappa_default_v2 = 'https://api.executableknowledge.org/kappa/v2/projects/default'


class KappaRuntime(object):
    def __init__(self, endpoint=None):
        """Create a Kappa client."""
        if not endpoint:
            self.url = kappa_default_v2
        else:
            self.url = endpoint

    def add_file(self, fname):
        """Add a file to the project."""
        with open(fname, 'rb') as f:
            content = f.read()

        resp = requests.get(self.url + '/files')
        file_list = [f['id'] for f in resp.json()]
        if fname in file_list:
            requests.delete(self.url + '/files/%s' % fname)

        file_data = {
            'metadata': {
                'compile': True,
                'id': fname,
                'position': 0,
                'version': [{
                    'client_id': 'foobar',
                    'local_version_file_version': 0
                    }]
                },
            'content': content
            }
        res = requests.post(self.url + '/files', data=json.dumps(file_data))
        return res

    def version(self):
        """Return the version of the Kappa environment."""
        try:
            res = requests.get(self.url)
            if res.status_code != 200:
                raise Exception('Kappa service returned with code: %s' %
                                res.status_code)
            content = res.json()
            version = content.get('project_version')
            return version
        except Exception as e:
            raise KappaRuntimeError(e)

    def parse(self, fname):
        """Parse given Kappa model code and throw exception if fails."""
        self.add_file(fname)
        parse_url = self.url + '/parse'
        res = requests.post(parse_url, data=json.dumps([]).encode('utf8'))
        #try:
        content = res.json()
        return content
        #except urllib2.HTTPError as e:
        #    if e.code == 400:
        #        error_details = json.loads(e.read())
        #        raise KappaRuntimeError(error_details)
        #    else:
        #        raise e
        #except urllib2.URLError as e:
        #    KappaRuntimeError(e.reason)

    def start(self, parameter):
        """Start a simulation with given parameters."""
        if 'max_time' not in parameter:
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
            raise KappaRuntimeError(e.reason)

        if connection.code == 200:
            text = connection.read()
            return int(json.loads(text))
        elif connection.code == 400:
            text = connection.read()
            error_details = json.loads(text)
            raise KappaRuntimeError(error_details)
        else:
            raise e

    def stop(self, token):
        """Stop a given simulation."""
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
            raise KappaRuntimeError(e.reason)

        if connection.code == 200:
            text = connection.read()
            return None
        elif connection.code == 400:
            text = connection.read()
            error_details = json.loads(text)
            raise KappaRuntimeError(error_details)
        else:
            raise e

    def status(self, token):
        """Return status of running simulation."""
        try:
            version_url = "{0}/process/{1}".format(self.url,token)
            response = urllib2.urlopen(version_url)
            text = response.read()
            return json.loads(text)
        except urllib2.HTTPError as e:
            if e.code == 400:
                error_details = json.loads(e.read())
                raise KappaRuntimeError(error_details)
            else:
                raise e
        except urllib2.URLError as e:
            KappaRuntimeError(e.reason)

    def shutdown(self,key):
        """Shutdown the server."""
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
            raise KappaRuntimeError(e.reason)
        if connection.code == 200:
            text = connection.read()
            return text
        elif connection.code == 400:
            text = connection.read()
            raise KappaRuntimeError(text)
        elif connection.code == 401:
            text = connection.read()
            raise KappaRuntimeError(text)
        else:
            raise e


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
            #print render_status(status).toString()
            print runtime.shutdown('6666')
        except KappaRuntimeError as e:
            print e.errors
