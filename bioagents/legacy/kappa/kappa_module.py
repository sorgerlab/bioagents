import sys
import logging
import argparse
import operator
import json

from kappa_client import KappaRuntime, KappaRuntimeError
from kqml import KQMLModule, KQMLPerformative, KQMLList
from bioagents import Bioagent

logger = logging.getLogger('Kappa')

def render_value(value):
    return str(value).encode('string-escape').replace('"', '\\"')


def render_status(status):
    reply_content = KQMLList()
    reply_content.add(":status")
    if 'plot' in status:
        plot_data = status['plot']
        plot = KQMLList()
        plot.add(':plot')
        if 'legend' in plot_data:
            legend = KQMLList()
            legend.add(':legend')
            for label in plot_data['legend']:
                legend.add('"'+label+'"')
            plot.add(legend)
        if 'observables' in plot_data:
            observables = KQMLList()
            observables.add(':observables')
            for o in plot_data['observables']:
                observation = KQMLList()
                observation.add(':observation')
                if 'time' in o:
                    time = KQMLList()
                    time.add(':time')
                    time.add(render_value(o['time']))
                    observation.add(time)
                if 'values' in o:
                    values = KQMLList()
                    values.add(':values')
                    for f in o['values']:
                        values.add(render_value(f))
                    observation.add(values)
                observables.add(observation)
            plot.add(observables)
        reply_content.add(plot)
    if 'tracked_events' in status:
        tracked_events = KQMLList()
        tracked_events.add(':tracked_events')
        tracked_events.add(render_value(status['tracked_events']))
        plot.add(tracked_events)
    if 'is_running' in status:
        is_running = KQMLList()
        is_running.add(':is_running')
        is_running.add(render_value(status['is_running']))
        plot.add(is_running)
    if 'event_percentage' in status:
        event_percentage = KQMLList()
        event_percentage.add(':event_percentage')
        event_percentage.add(render_value(status['event_percentage']))
        plot.add(event_percentage)
    if 'time_percentage' in status:
        time_percentage = KQMLList()
        time_percentage.add(':time_percentage')
        time_percentage.add(render_value(status['time_percentage']))
        plot.add(time_percentage)
    if 'time' in status:
        time = KQMLList()
        time.add(':time')
        time.add(render_value(status['time']))
        plot.add(time)
    if 'event' in status:
        event = KQMLList()
        event.add(':event')
        event.add(render_value(status['event']))
        plot.add(event)
    # trips is not happy with this not sure why
    # if 'log_messages':
    #     log_messages = KQMLList()
    #     log_messages.add(':log_messages')
    #     for message in status['log_messages']:
    #         log_messages.add("'"+render_value(message)+"'")
    #     plot.add(log_messages)
    return reply_content


class Kappa_Module(Bioagent):
    '''
    The Kappa module is a TRIPS module built around the Kappa client. Its role
    is to receive and decode messages and send responses from and to other
    agents in the system.
    '''
    name = 'Kappa'
    tasks = ['KAPPA-VERSION', 'KAPPA-PARSE', 'KAPPA-START',
             'KAPPA-STATUS', 'KAPPA-STOP']
    def __init__(self, **kwargs):
        # Call the constructor of TripsModule
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url", help="kappa endpoint")
        args = parser.parse_args()
        if args.kappa_url:
            self.kappa_url = args.kappa_url
        else:
            logger.error('No Kappa URL given.')
            sys.exit()
        
        # Instantiate a kappa runtime
        self.kappa = KappaRuntime(self.kappa_url)
        
        super(Kappa_Module, self).__init__(**kwargs)
        return

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        content_list = content
        task_str = content_list[0].to_string().upper()
        arguments = self.request_arguments(content_list)
        if task_str == 'KAPPA-VERSION':
            try:
                reply_content = self.respond_version()
            except Exception as e:
                message = 'Could not get Kappa version: (%s)' % e
                return self.error_reply(msg, message)
        elif task_str == 'KAPPA-PARSE':
            try:
                reply_content = self.respond_parse(arguments)
            except Exception as e:
                message = 'Could not parse Kappa model: (%s)' % e
                return self.error_reply(msg, message)
        elif task_str == 'KAPPA-START':
            try:
                reply_content = self.respond_start(arguments)
            except Exception as e:
                message = 'Could not start Kappa simulation: (%s)' % e
                return self.error_reply(msg, message)
        elif task_str == 'KAPPA-STATUS':
            try:
                reply_content = self.respond_status(arguments)
            except Exception as e:
                message = 'Could not get Kappa status: (%s)' % e
                return self.error_reply(msg, message)
        elif task_str == 'KAPPA-STOP':
            try:
                reply_content = self.respond_stop(arguments)
            except Exception as e:
                message = 'Could not stop Kappa simulation: (%s)' % e
                return self.error_reply(msg, message)
        else:
            message = '"unknown request task ' + task_str + '"'
            return self.error_reply(msg, message)
        return self.reply_with_content(msg, reply_content)

    def respond_version(self):
        '''
        Response content to version message
        '''
        response = self.kappa.version()
        reply_content = KQMLList.from_string(
                        '(SUCCESS ' +
                             ':VERSION "%s" ' % response['version'] +
                             ':BUILD   "%s")' % response['build'])
        logger.debug(reply_content.to_string())
        return reply_content

    def response_error(self, error):
        reply_content = KQMLList()
        for e in error:
            error_msg = '"%s"' %\
                str(e).encode('string-escape').replace('"', '\\"')
            reply_content.add(error_msg)
        return self.format_error(reply_content.to_string())

    def request_arguments(self, arguments):
        request = {}
        arg_list = [arguments[index] for index in
                    range(arguments.length())]
        for i, a in enumerate(arg_list):
            arg_str = a.to_string()
            if arg_str.startswith(':'):
                key = arg_str[1:].upper()
                val = arg_list[i+1].to_string()
                request[key] = val
        logger.debug(request)
        return request

    def respond_parse(self, arguments):
        '''
        Response content to parse message
        '''
        if "CODE" not in arguments:
            reply_content = self.response_error(["Missing code"])
        else:
            request_code = arguments["CODE"]
            request_code = request_code[1:-1]
            logger.debug('raw {0}'.format(request_code))
            request_code = request_code.decode('string_escape')
            logger.debug('respond_parse {0}'.format(request_code))
            reply_content = KQMLList()
            try:
                response = self.kappa.parse(request_code)
                logger.debug(response)
                reply_content = KQMLList.from_string('(SUCCESS)')
            except KappaRuntimeError as e:
                logger.debug(e.errors)
                reply_content = self.response_error(e.errors)
        return reply_content

    def format_error(self, message):
        response_content = KQMLList.from_string(
                            '(FAILURE :reason %s)' % message)
        return response_content

    def respond_start(self, arguments):
        '''
        Response content to start message
        '''
        if "CODE" not in arguments:
            response_content = self.response_error(["Missing code"])
        elif "NB_PLOT" not in arguments:
            response_content =\
                self.response_error(["Missing number of plot points"])
        else:
            try:
                parameter = {}
                parameter["nb_plot"] = arguments["NB_PLOT"]
                if "MAX_TIME" in arguments:
                    parameter["max_time"] = float(arguments["MAX_TIME"])
                if "MAX_EVENTS" in arguments:
                    parameter["max_events"] = int(arguments["MAX_EVENTS"])
                request_code = arguments["CODE"]
                request_code = request_code[1:-1]
                request_code = request_code.decode('string_escape')
                parameter["code"] = request_code
                try:
                    logger.debug(parameter)
                    response = self.kappa.start(parameter)
                    response_message = '(SUCCESS :id %d)' % response
                    response_content = KQMLList.from_string(response_message)
                except KappaRuntimeError as e:
                    response_content = self.response_error(e.errors)
            except ValueError as e:
                response_content = self.response_error([str(e)])
        return response_content

    def respond_status(self, arguments):
        if "ID" not in arguments:
            response_content = self.response_error(["Missing simulation id"])
        else:
            try:
                token = int(arguments["ID"])
                status = self.kappa.status(token)
                response_content = render_status(status)
            except ValueError as e:
                response_content = self.response_error([str(e)])
            except KappaRuntimeError as e:
                response_content = self.response_error(e.errors)
        return response_content

    def respond_stop(self, arguments):
        if "ID" not in arguments:
            response_content = self.response_error(["Missing simulation id"])
        else:
            try:
                token = int(arguments["ID"])
                status = self.kappa.stop(token)
                response_content = KQMLList.from_string('(SUCCESS)')
            except KappaRuntimeError as e:
                response_content = self.response_error(e.errors)
        return response_content

if __name__ == "__main__":
    km = Kappa_Module(argv=sys.argv[1:])
