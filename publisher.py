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
CFG='./master.json'

def get_config():
    if not os.path.exists(CFG):
        print CFG + ' file does not exist'
        sys.exit(1)

    try:
        fp = open(CFG, 'r')
    except IOError, e:
        print ('Failed to execute ' + message['cmd'] + ' (%d) %s \n' % (e.errno, e.strerror))
    
    try:
        global CONFIG
        CONFIG=json.load(fp)
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

    if len(sys.argv) == 1:
        print >>sys.stderr, 'Missing options'
        usage()
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ht:s:c:w:n:', ['help', 'type', 'schedule', 'command', 'with', 'without'])
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
        elif o in ('-w', '--with'):
                with  = a
        elif o in ('-n', '--without'):
                without  = a

    if type is None:
        print >>sys.stderr, 'Please provide type'
        usage()

    if type == 'cli' and cmd is None:
        print >>sys.stderr, 'Please provide command'
        usage()

    run (type, schedule, cmd)

# Signal handler
def master_timeout(signum, frame):
    print 'Timeout reached - exiting'
    sys.exit(1)

# When timeout happens master_timeout definition executes raising an exception
signal.signal(signal.SIGALRM, master_timeout)

def type_ping (output, hostname):
    response_time = round( (time.time() - float(output)) * 1000, 2 )
    response_str = '>>>>>> ' + hostname + ' - response time: ' + str(response_time) + ' ms'

    return response_str

def type_cli (output, hostname, rc):
    response_str = '>>>>>> ' + hostname + ' ('+str(rc)+')  :\n' +  str(output)

    return response_str

def receive_msgs (read_queue, org, old_msgs, agent_msgs):
    response = None
    responses = list()

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
        output = response['output']
        msg_id = str(response['msg_id'])
        type = str(response['type'])
        hostname = str(response['hostname'])
        rc = response['rc']

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

        if ( type == 'discovery' or type == 'ping' ):
            responses.append(type_ping (output, hostname))
        elif type == 'count':
            responses.append(1)
        elif type == 'cli':
            responses.append(type_cli(output, hostname, rc))
        else:
            responses.append('Unknown type response from agent ' + type)

        # We're done with the message - delete it
        if not read_queue.delete_message(rmsg):
            print 'Failed to delete reponse message'

    # Retrun all responses
    return (responses, old_msgs, agent_msgs)

def delete_org_message (write_queue, org):
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


def run(type, schedule, cmd):

    # Get configuration
    get_config()

    # Connect with key, secret and region
    conn = connect_to_region(CONFIG['aws']['region'])
    write_queue = conn.get_queue(CONFIG['aws']['write_queue'])
    read_queue = conn.get_queue(CONFIG['aws']['read_queue'])

    message={'type': type, 'schedule':schedule, 'cmd':cmd, 'ts':time.time()};
    message_json=json.dumps(message)
    
    # Write a messages
    message = write_queue.new_message(message_json)
    
    org = write_queue.write(message)
    if org.id is None:
        print 'Failed to write command to queue'
        exit
   
    # 15 second initial timeout  
    signal.alarm(CONFIG['general']['timeout'])
    offset=int(time.time())

    old_msgs={}
    agent_msgs={}
    agent_count=0

    while ( True ):
        responses, old_msgs, agent_msgs = receive_msgs (read_queue, org, old_msgs, agent_msgs)
        if responses:
            agent_count += len(responses)
            if type != 'count':
                for response in responses:
                    print response
            # Everytime we receive a message we wait 5 more seconds
            offset=int(time.time())

        if (int(time.time()) - offset) >= 2:
           if type == 'count':
               print str(agent_count)
           else:
               print ''
               print str(agent_count) + ' agent(s) responded'
           break
    signal.alarm(0)
    
    signal.alarm(CONFIG['general']['timeout'])
    while ( True ):
        rm_org_msg = delete_org_message (write_queue, org)
        if rm_org_msg is True:
            break
    signal.alarm(0)

if __name__ == "__main__":
    sys.exit(main())
