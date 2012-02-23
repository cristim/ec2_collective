#!/bin/env python
# coding: utf-8

from boto.sqs import connect_to_region
from boto.exception import SQSError
import simplejson as json
import time
import signal
import sys
import getopt
import os
import random
import string

# CFG FILE
CFILE='./master.json'

def get_config():
    if not os.path.exists(CFILE):
        print CFILE + ' file does not exist'
        sys.exit(1)

    try:
        fp = open(CFILE, 'r')
    except IOError, e:
        print ('Failed to open ' + CFILE + ' (%d) %s \n' % (e.errno, e.strerror))
    
    try:
        global CFG
        CFG=json.load(fp)
    except (TypeError, ValueError), e:
        print 'Error in configuration file'
        sys.exit(1)

def usage():
    print >>sys.stderr, '    Usage:'
    print >>sys.stderr, '    ' + sys.argv[0] + ' -f [ping|cli|script|s3] -c <command>'
    sys.exit(1)

def main():

    # Get configuration
    get_config()

    # Defaults
    func='ping'
    schedule=time.time()
    cmd=None
    wf=None
    wof=None
    timeout=int(CFG['general']['default_timeout'])

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hf:s:c:w:n:t:', ['help', 'func=', 'schedule=', 'command=', 'wf=', 'wof=', 'timeout='])
    except getopt.GetoptError, err:
        print >>sys.stderr, str(err) 
        return 1

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-f', '--func'):
            if a not in ['ping', 'count', 'cli', 'script', 's3' ]:
                print 'Uknown function: ' + str(a)
                usage()
            else:
                func = a
        elif o in ('-s', '--schedule'):
            if a != 'now':
                # We use the following ts MMDDHHMM
                schedule=a
        elif o in ('-c', '--command'):
            cmd = a
        elif o in ('-w', '--wf'):
            wf = a
        elif o in ('-n', '--wof'):
            wof = a
        elif o in ('-t', '--timeout'):
            try:
                timeout = int(a)
            except:
                print 'Timeout value is not an integer'
                sys.exit(1)

    if func is None:
        print >>sys.stderr, 'Please provide function'
        usage()

    if func == 'cli' and cmd is None:
        print >>sys.stderr, 'Please provide command'
        usage()

    if func == 'script' and cmd is None:
        print >>sys.stderr, 'Please provide path to script with -c|--command'
        usage()

    run (func, schedule, cmd, wf, wof, timeout)

# Signal handler
def master_timeout(signum, frame):
    print 'Timeout reached - exiting'
    sys.exit(1)

# When timeout happens master_timeout definition executes raising an exception
signal.signal(signal.SIGALRM, master_timeout)

def func_ping_response (responses):
    for response in responses:
        hostname = str(responses[response]['hostname'])
        output = str(responses[response]['output'])

        response_time = round( (time.time() - float(output)) * 1000, 2 )
        response_str = hostname + ' time=' + str(response_time) + ' ms'

        print response_str

def func_cli_response (responses):
    for response in responses:
        hostname = str(responses[response]['hostname'])
        output = str(responses[response]['output'])
        rc = str(responses[response]['rc'])

        response_str = '>>>>>> ' + hostname + ' exit code: ('+str(rc)+'):\n' +  str(output)

        print response_str

def receive_responses (read_queue, org_ids, func, timeout, display, discovered=None):

    if func in [ 'ping','discovery','count']:
        timeout=CFG['general']['ping_timeout']

    total_responses = {}
    old_msgs = {}
    agent_msgs = {}

    start_time=int(time.time())
    while ( True ):
        responses, old_msgs, agents_msgs = pull_msgs (read_queue, org_ids, func, old_msgs, agent_msgs)
        if len(responses) > 0:
            total_responses.update(responses)

            if func in [ 'ping','discovery','count'] and display == 'display':
                func_ping_response(responses)

            if func in ['cli', 'script' ] and display == 'display':
                func_cli_response(responses)

        if discovered is not None and len(total_responses) >= discovered:
            break

        if ((int(time.time()) - start_time) >= timeout):
            break

    return total_responses

def pull_msgs (read_queue, org_ids, org_func, old_msgs, agent_msgs):

    response = None
    responses = {}

    # Receive at least 1 message be fore continuing 
    rmsgs = read_queue.get_messages(num_messages=10, visibility_timeout=2)

    # For each message we check for duplicate, and if it is a response to our org message
    for rmsg in rmsgs:

        # PUT FIRST Avoid duplicates 
        if rmsg.id in old_msgs:
            continue
        else:
            old_msgs[rmsg.id] = rmsg.id

        response=json.loads(rmsg.get_body())
        msg_id = str(response['msg_id'])
        func = str(response['func'])
        hostname = str(response['hostname'])

        # Is it a response to our original request
        if msg_id not in org_ids:
            # Dont handle it again
            old_msgs[rmsg.id] = rmsg.id
            continue

        if hostname in agent_msgs:
            old_msgs[rmsg.id] = rmsg.id
            if not read_queue.delete_message(rmsg):
                print 'Failed to delete reponse message'
            continue
        else:
            agent_msgs[hostname] = hostname

        if ( org_func != func ):
            print 'Type differs from original! (' + str(org_func) + ') != (' + str(func) + ')' ' - skipping'
            old_msgs[rmsg.id] = rmsg.id
            continue

        responses[hostname] = response

        # We're done with the message - delete it
        if not read_queue.delete_message(rmsg):
            print 'Failed to delete reponse message'

    # Retrun all responses
    return (responses, old_msgs, agent_msgs)

def delete_org_message (write_queue, msg_ids):

    signal.alarm(CFG['general']['clean_timeout'])

    while ( True ):
        msg_ids = pull_org_msgs (write_queue, msg_ids)
        if len(msg_ids) == 0:
            break

    signal.alarm(0)

def pull_org_msgs(write_queue, msg_ids):

    # Pick up written message and delete it
    wmsgs = write_queue.get_messages(num_messages=10, visibility_timeout=2)
    
    for wmsg in wmsgs:
    
        if wmsg.id in msg_ids:
            if not write_queue.delete_message(wmsg):
                print 'Failed to original reponse message'
                continue
            else:
                del msg_ids[wmsg.id]
        else:
            continue

    return msg_ids

def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

def dict_to_sqs_obj(message, write_queue):

    message_json=json.dumps(message)
    message = write_queue.new_message(message_json)

    return message

def write_msg (write_queue, dict_message):

    message=dict_to_sqs_obj(dict_message, write_queue)
    org_ids={}

    written=False
    for i in range(0, 3):
        try:
            org = write_queue.write(message)
        except:
            print 'Failed to write command message'
            sys.exit(1)

        if org.id is None:
            print 'Failed to write 1 command message'
        else:
            written=True
            org_ids[org.id] = org.id

    if written is True:
        return org_ids
    else:
        print 'Failed to write any command messages'
        sys.exit(1)

def inhale_script (script_file):
    if not os.path.exists(script_file):
        print script_file + ' file does not exist'
        sys.exit(1)

    f = open(script_file, 'r')

    return f.read()

def run(func, schedule, cmd, wf, wof, timeout):

    if func == 'script':
        payload = inhale_script(cmd)
        cmd = os.path.basename(cmd)
    else:
        payload = None

    responses={}
    ping_responses={}
    org_ids={}

    # Connect with key, secret and region
    conn = connect_to_region(CFG['aws']['region'])
    write_queue = conn.get_queue(CFG['aws']['write_queue'])
    read_queue = conn.get_queue(CFG['aws']['read_queue'])

    # Construct message
    message={'func':func,'schedule':schedule, 'cmd':cmd, 'ts':time.time(), 'wf':wf, 'wof':wof, 'batch_msg_id':id_generator(), 'payload':payload}

    # 15 second initial timeout  
    if func == 'count':
        org_ids.update (write_msg(write_queue, message))

        responses = receive_responses (read_queue, org_ids, func, timeout, 'nodisplay')
	print str(len(responses))

    if func == 'ping' or func == 'discovery':
        org_ids.update (write_msg(write_queue, message))
        responses = receive_responses (read_queue, org_ids, func, timeout, 'display')

    if func == 'cli':
        # Perform a ping to figure out how many replies to expect
        message['func'] = 'count'
        count_ids =  (write_msg(write_queue, message))
        org_ids.update (count_ids)
        ping_responses = receive_responses (read_queue, count_ids, 'count', timeout, 'nodisplay')
        # Perform the actual command wait for all agents to return until timeout
        message['func'] = 'cli'
        message['batch_msg_id'] = id_generator()
        cli_ids =  (write_msg(write_queue, message))
        org_ids.update (cli_ids)
        responses = receive_responses (read_queue, cli_ids, func, timeout, 'display', len(ping_responses))

    if func == 'script':
        # Perform a ping to figure out how many replies to expect
        message['func'] = 'count'
        count_ids =  (write_msg(write_queue, message))
        org_ids.update (count_ids)
        ping_responses = receive_responses (read_queue, count_ids, 'count', timeout, 'nodisplay')
        # Perform the actual command wait for all agents to return until timeout
        message['func'] = 'script'
        message['batch_msg_id'] = id_generator()
        cli_ids =  (write_msg(write_queue, message))
        org_ids.update (cli_ids)
        responses = receive_responses (read_queue, cli_ids, func, timeout, 'display', len(ping_responses))

    # Delete original messags
    delete_org_message (write_queue, org_ids)

    if len(ping_responses) != len(responses):
        for hostname in ping_responses.keys():
            if not hostname in responses:
                print 'Timeout in response from: ' + hostname


if __name__ == "__main__":
    sys.exit(main())
