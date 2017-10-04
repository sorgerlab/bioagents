"""Web API client for a Kappa simulator."""

import urllib2
import json
import os
import re
import requests
import pickle
from datetime import datetime
from time import sleep


class KappaRuntimeError(Exception):
    def __init__(self, resp):
        self.error = resp.reason
        self.text = re.findall(
            'u?[\"\']text[\"\']: ?u?[\"\'](.*?)[\"\'],',
            resp.content
            )
        try:
            now = datetime.now()
            pkl_name = '%s_err_resp.pkl' % now.strftime('%Y%m%d-%H%M%S')
            with open(pkl_name, 'wb') as f:
                pickle.dump(resp, f, protocol=2)
            print("Pickled response for further analysis.")
            print("See %s" % os.path.abspath(pkl_name))
        except Exception:
            print("Failed to pickle response for further analysis.")
        return

    def __str__(self):
        msg = "Kappa failed with error: %s." % self.error
        if self.text:
            msg += "\nThe following text was found: %s." % ', '.join(self.text)
        return msg


class KappaRuntime(object):
    kappa_url = 'https://api.executableknowledge.org/kappa/v2/projects'

    def __init__(self, project_name='default'):
        """Create a Kappa client."""
        resp = self.dispatch('get', self.kappa_url)
        if resp.status_code is not 200:
            raise KappaRuntimeError(resp)
        project_list = [t['project_id'] for t in resp.json()]
        if project_name is not 'default':
            if project_name in project_list:
                resp = self.dispatch(
                    'delete',
                    self.kappa_url + '/' + project_name
                    )
            resp = self.dispatch(
                'post',
                self.kappa_url,
                {'project_id': project_name}
                )
        self.url = self.kappa_url + '/' + project_name
        return

    def dispatch(self, method, url, data=None):
        """Send a request of type method to the project."""
        if not hasattr(requests, method):
            raise AttributeError('Requests does not have method %s.' % method)
        if data is not None:
            data = json.dumps(data).encode('utf8')
        resp = getattr(requests, method)(url, data=data)
        if resp.status_code is not 200:
            raise KappaRuntimeError(resp)
        return resp

    def get_files(self):
        """Get a list of files in this project."""
        resp = self.dispatch('get', self.url + '/files')
        return [f['id'] for f in resp.json()]

    def add_file(self, fname):
        """Add a file to the project."""
        with open(fname, 'rb') as f:
            content = f.read()

        file_list = self.get_files()
        if fname in file_list:
            requests.delete(self.url + '/files/%s' % fname)

        return self.add_code(content, fname)

    def add_code(self, code_str, name=None):
        """Add a code string to the project."""
        if name is None:
            fname_list = self.get_files()
            fmt = "bioagent_%d.ka"
            i = 0
            while fmt % i in fname_list:
                i += 1
            name = fmt % i
        file_data = {
            'metadata': {
                'compile': True,
                'id': name,
                'position': 0,
                'version': [{
                    'client_id': 'foobar',
                    'local_version_file_version': 0
                    }]
                },
            'content': code_str
            }
        self.dispatch('post', self.url + '/files', file_data)
        return

    def version(self):
        """Return the version of the Kappa environment."""
        try:
            res = self.dispatch('get', self.url)
            content = res.json()
            version = content.get('project_version')
            return version
        except Exception as e:
            raise KappaRuntimeError(e)

    def compile(self, fname_list=None, code_list=None):
        """Parse given Kappa files and any other files that have been added.

        Parameters
        ----------
        fname_list : List or None
            A list of local file names (ending in `.ka`) to be added to the
            project before compiling. None by default, indicating no new files.
        code_list : List or None
            A list of code strings to be added to the project before compiling.
            None by default, indicating no new strings.
        """
        for fname in [] if fname_list is None else fname_list:
            self.add_file(fname)
        for code_str in [] if code_list is None else code_list:
            self.add_code(code_str)
        res = self.dispatch('post', self.url + '/parse', [])
        content = res.json()
        return content

    def start(self, **parameters):
        """Start a simulation with given parameters.

        Note that parameters are subject to changes in the kappa remote api.

        Parameters
        ----------
        plot_period : int or float
            The period of the plot perhaps?
        pause_condition : string or None
            I'm sure there are some options for this, but I have no idea what
            they are. Default None
        seed: int
            A random seed for the simulation, I expect.
        store_trace : bool
            Presumably you can choose whether to store the trace. Hopefully
            interpretation is straightforward. Default True.
        """
        complete_params = {
            'plot_period': 10,
            'pause_condition': '',
            'seed': None,
            'store_trace': True
            }
        complete_params.update(parameters)
        resp = self.dispatch('post', self.url + '/simulation', complete_params)
        return resp.json()

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
