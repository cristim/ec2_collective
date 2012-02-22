#!/bin/env python
# coding: utf-8

from boto.sqs import connect_to_region
import simplejson as json
import time
import signal
import sys
import getopt
import os

# CFG FILE
CFILE='./master.json'

def get_config():
    if not os.path.exists(CFILE):
        print CFILE + ' file does not exist'
        sys.exit(1)

    try:
        fp = open(CFILE, 'r')
    except IOError, e:
        print ('Failed to execute ' + message['cmd'] + ' (%d) %s \n' % (e.errno, e.strerror))
    
    try:
        global CFG
        CFG=json.load(fp)
    except (TypeError, ValueError), e:
        print 'Error in configuration file'
        sys.exit(1)

def usage():
    print >>sys.stderr, '    Usage:'
    print >>sys.stderr, '    ' + sys.argv[0] + ' -t [ping|cli|script|s3] -c <command>'
    sys.exit(1)


def main():

    # Defaults
    type=None
    schedule=time.time()
    cmd=None
    wf=None
    wof=None

    if len(sys.argv) == 1:
        print >>sys.stderr, 'Missing options'
        usage()
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ht:s:c:w:n:', ['help', 'type=', 'schedule=', 'command=', 'wf=', 'wof='])
    except getopt.GetoptError, err:
        print >>sys.stderr, str(err) 
        return 1

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-t', '--type'):
            if a not in ['ping', 'count', 'cli', 'script', 's3' ]:
                print 'Uknown type: ' + str(a)
                usage()
            else:
                type = a
        elif o in ('-s', '--schedule'):
            if a != 'now':
                # We use the following ts MMDDHHMM
                schedule=a
        elif o in ('-c', '--command'):
                cmd  = a
        elif o in ('-w', '--wf'):
                wf  = a
        elif o in ('-n', '--wof'):
                wof  = a

    if type is None:
        print >>sys.stderr, 'Please provide type'
        usage()

    if type == 'cli' and cmd is None:
        print >>sys.stderr, 'Please provide command'
        usage()

    run (type, schedule, cmd, wf, wof)

# Signal handler
def master_timeout(signum, frame):
    print 'Timeout reached - exiting'
    sys.exit(1)

# When timeout happens master_timeout definition executes raising an exception
signal.signal(signal.SIGALRM, master_timeout)

def type_ping_response (response):
    hostname = str(response['hostname'])
    output = str(response['output'])

    response_time = round( (time.time() - float(output)) * 1000, 2 )
    response_str = '>>>>>> ' + hostname + ' - response time: ' + str(response_time) + ' ms'

    return response_str

def type_cli_response (response):
    hostname = str(response['hostname'])
    output = str(response['output'])
    rc = response['rc']

    response_str = '>>>>>> ' + hostname + ' ('+str(rc)+'):\n' +  str(output)

    return response_str

def receive_responses (read_queue, org, type):

    timeout=CFG['general']['default_timeout']
    total_responses = {}
    old_msgs = {}
    agent_msgs = {}

    start_time=int(time.time())
    while ( True ):
        responses, old_msgs, agents_msgs = pull_msgs (read_queue, org, type, old_msgs, agent_msgs)
        if len(responses) > 0:
            total_responses.update(responses)
        if ( (int(time.time() - start_time) >= CFG['general']['timeout_next_response']  ) and 
              len(total_responses)  > 0 ):
                break
        if (int(time.time()) - start_time) >= timeout:
            break

    return total_responses

def pull_msgs (read_queue, org, org_type, old_msgs, agent_msgs):

    response = None
    responses = {}

    # Receive at least 1 message be fore continuing 
    rmsgs = read_queue.get_messages(num_messages=10, visibility_timeout=5)

    # For each message we check for duplicate, and if it is a response to our org message
    for rmsg in rmsgs:

        # PUT FIRST Avoid duplicates 
        if rmsg.id in old_msgs:
            continue
        else:
            old_msgs[rmsg.id] = rmsg.id

        response=json.loads(rmsg.get_body())
        msg_id = str(response['msg_id'])
        type = str(response['type'])
        hostname = str(response['hostname'])

        # Is it a response to our original request
        if msg_id != org.id:
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

        if ( org_type != type ):
            print 'Type differs from original! (' + str(org_type) + ') != (' + str(type) + ')' ' - skipping'
            old_msgs[rmsg.id] = rmsg.id
            continue

        responses[hostname] = response

        # We're done with the message - delete it
        if not read_queue.delete_message(rmsg):
            print 'Failed to delete reponse message'

    # Retrun all responses
    return (responses, old_msgs, agent_msgs)

def delete_org_message (write_queue, org):

    signal.alarm(CFG['general']['clean_timeout'])

    while ( True ):
        if pull_org_msgs (write_queue, org):
            break

    signal.alarm(0)

def pull_org_msgs(write_queue, org):

    # Pick up written message and delete it
    wmsgs = write_queue.get_messages(num_messages=10, visibility_timeout=10)
    
    for wmsg in wmsgs:
    
        if wmsg.id == org.id:
            if not write_queue.delete_message(wmsg):
                print 'Failed to original reponse message'
                return False
            return True
        else:
            return False

    return False

def write_msg (queue, message):

    message_json=json.dumps(message)

    message = queue.new_message(message_json)

    org = queue.write(message)
    if org.id is None:
        print 'Failed to write command to queue'
        sys.exit(main())
    else:
        return org

def run(type, schedule, cmd, wf, wof):

    responses={}
    ping_responses={}

    # Get configuration
    get_config()

    # Connect with key, secret and region
    conn = connect_to_region(CFG['aws']['region'])
    write_queue = conn.get_queue(CFG['aws']['write_queue'])
    read_queue = conn.get_queue(CFG['aws']['read_queue'])

    # Construct message
    message={'type':type,'schedule':schedule, 'cmd':cmd, 'ts':time.time(), 'wf':wf, 'wof':wof}

    # 15 second initial timeout  
    if type == 'count':
        message['type'] =  type
        org = write_msg(write_queue, message)
        responses = receive_responses (read_queue, org, type)

        delete_org_message (write_queue, org)

	print str(len(responses))

    if type == 'ping' or type == 'discovery':
        message['type'] =  type
        org = write_msg(write_queue, message)
        responses = receive_responses (read_queue, org, type)

        for response in responses:
            print type_ping_response(responses[response])

    elif type == 'cli':
        message['type'] = 'count'
        org = write_msg(write_queue, message)
        ping_responses = receive_responses (read_queue, org, 'count')

        delete_org_message (write_queue, org)

	print 'We expect answers from: ' + str(len(ping_responses)) + ' agents'

        message['type'] = 'cli'
        org = write_msg(write_queue, message)
        responses = receive_responses (read_queue, org, type)

        delete_org_message (write_queue, org)

        for response in responses:
            print type_cli_response(responses[response])

        if len(ping_responses) != len(responses):
            for hostname in ping_responses.keys():
                if not hostname in responses:
                    print 'Timeout in response from: ' + hostname


if __name__ == "__main__":
    sys.exit(main())
