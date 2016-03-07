import sys
import argparse
import operator
import json

from jnius import autoclass, cast
from TripsModule import trips_module
from kappa_client import KappaRuntime, RuntimeError

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

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
    if 'log_messages':
        log_messages = KQMLList()
        log_messages.add(':log_messages')
        for message in status['log_messages']:
            log_messages.add("'"+render_value(message)+"'")
        plot.add(log_messages)        
    return reply_content


class Kappa_Module(trips_module.TripsModule):
    '''
    The Kappa module is a TRIPS module built around the Kappa client. Its role
    is to receive and decode messages and send responses from and to other
    agents in the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(Kappa_Module, self).__init__(argv)
        self.tasks = {'ONT::PERFORM': ['ONT::VERSION']}
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url"
                           ,help="kappa endpoint")
        args = parser.parse_args()
        if args.kappa_url:
            self.kappa_url=args.kappa_url

    def init(self):
        '''
        Initialize Kappa module
        '''
        super(Kappa_Module, self).init()
        # Send subscribe messages
        for task, subtasks in self.tasks.iteritems():
            for subtask in subtasks:
                msg_txt = '(subscribe :content (request &key :content ' +\
                    '(%s &key :content (%s . *))))' % (task, subtask)
                self.send(KQMLPerformative.fromString(msg_txt))
        # Instantiate a kappa runtime
        self.kappa = KappaRuntime(self.kappa_url)
        # Send ready message
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        print msg
        content_list = cast(KQMLList, content)
        task_str = content_list.get(0).toString().upper()
        if task_str == 'ONT::PERFORM':
            subtask = cast(KQMLList,content_list.getKeywordArg(':content'))
            subtask_str = subtask.get(0).toString().upper()
            subtask.remove(0)
            arguments = self.request_arguments(subtask)
            if subtask_str == 'ONT::VERSION':
                reply_content = self.respond_version()
            elif subtask_str == 'ONT::PARSE':
                reply_content = self.respond_parse(arguments)
            elif subtask_str == 'ONT::START':
                reply_content = self.respond_start(arguments)
            elif subtask_str == 'ONT::STATUS':
                reply_content = self.respond_status(arguments)
            elif subtask_str == 'ONT::STOP':
                reply_content = self.respond_stop(arguments)
            else:
                message = '"'+'unknown request subtask ' + subtask_str + '"'
                self.error_reply(msg,message)
                return
        else:
            message = '"'+'unknown request task ' + task_str + '"'
            self.error_reply(msg,message)
            return
        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)

    def respond_version(self):
        '''
        Response content to version message
        '''
        reply_content = KQMLList()
        response = self.kappa.version()
        response_content = KQMLList.fromString( '' +\
                        '(ONT::KAPPA ' +\
                             '( ONT::VERSION "%s") ' % response['version'] +\
                             '( ONT::BUILD   "%s") ' % response['build']   +\
                        ')')
        reply_content.add(KQMLList(response_content))
        return reply_content
    def response_error(self,error):
        reply_content = KQMLList()
        for e in error:
            error_msg = '"%s"' % str(e).encode('string-escape').replace('"', '\\"')
            reply_content.add(error_msg)
        return self.format_error(reply_content.toString())

    def request_arguments(self,arguments):
        request = dict()
        for index in range(arguments.size()):
            key_value = arguments.get(index)
            key_value = cast(KQMLList, key_value)
            if key_value.size() > 1:
                request[key_value.get(0).toString()] = key_value.get(1).toString()
        return request

    def respond_parse(self,arguments):
        '''
        Response content to parse message
        '''
        if not "ONT::CODE" in arguments:
            reply_content = self.response_error(["Missing code"])
        else:
            request_code = arguments["ONT::CODE"]
            request_code = request_code[1:-1]
            print 'raw {0}'.format(request_code)
            request_code = request_code.decode('string_escape')
            print 'respond_parse {0}'.format(request_code)
            reply_content = KQMLList()
            try: 
                response = self.kappa.parse(request_code)
                print response
                response_content = KQMLList.fromString('(ONT::KAPPA ( ONT::OK ) )')
                reply_content.add(KQMLList(response_content))
            except RuntimeError as e:
                print e.errors
                reply_content = self.response_error(e.errors)
        return reply_content

    def format_error(self,message):
        response_content = KQMLList.fromString( '' +\
                        '(ONT::KAPPA ' +\
                             '( ONT::ERRORS %s) ' % message +\
                        ')')
        return response_content
    
    def respond_start(self,arguments):
        '''
        Response content to start message
        '''
        if not "ONT::CODE" in arguments:
            response_content = self.response_error(["Missing code"])
        elif not "ONT::NB_PLOT" in arguments:
            response_content = self.response_error(["Missing number of plot points"])
        else:
            try:
                parameter = dict()
                parameter["nb_plot"] = arguments["ONT::NB_PLOT"]
                if "ONT::MAX_TIME" in arguments:
                    parameter["max_time"] = float(arguments["ONT::MAX_TIME"])
                if "ONT::MAX_EVENTS" in arguments:
                    parameter["max_events"] = int(arguments["ONT::MAX_EVENTS"])
                request_code = arguments["ONT::CODE"]
                request_code = request_code[1:-1]
                request_code = request_code.decode('string_escape')
                parameter["code"] = request_code
                try: 
                    print parameter
                    response = self.kappa.start(parameter)
                    response_message = '(ONT::KAPPA ( ONT::TOKEN %d ) )' % response
                    response_content = KQMLList.fromString(response_message)
                except RuntimeError as e:
                    response_content = self.response_error(e.errors)
            except ValueError as e:
                response_content = self.response_error([str(e)])
        return response_content

    def respond_status(self,arguments):
        if not "ONT::TOKEN" in arguments:
            response_content = self.response_error(["Missing token"])
        else:
            try:
                token = int(arguments["ONT::TOKEN"])
                status = self.kappa.status(token)
                response_content = render_status(status)
            except ValueError as e:
                response_content = self.response_error([str(e)])
            except RuntimeError as e:
                response_content = self.response_error(e.errors)
        return response_content

    def respond_stop(self,arguments):
        if not "ONT::TOKEN" in arguments:
            response_content = self.response_error(["Missing token"])
        else:
            try:
                token = int(arguments["ONT::TOKEN"])
                status = self.kappa.stop(token)
                response_content = KQMLList.fromString('(ONT::KAPPA ( ONT::OK ) )')
            except RuntimeError as e:
                response_content = self.response_error(e.errors)
        return response_content

if __name__ == "__main__":
    dm = Kappa_Module(['-name', 'Kappa'] + sys.argv[1:])
    dm.run()
