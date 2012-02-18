#!/bin/env python
# coding: utf-8

from boto.sqs import connect_to_region
import simplejson as json
import time
import signal
import sys
import getopt

# These will later be put in a config file
REGION='eu-west-1'
WRITE_QUEUE='master'
READ_QUEUE='agent'
TIMEOUT=15

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
        run()
    except getopt.error, msg:
        print >>sys.stderr, err.msg
        print >>sys.stderr, "for help use --help"
        return 2

# Signal handler
def master_timeout(signum, frame):
    print 'Timeout reached - exiting'
    exit

# When timeout happens master_timeout definition executes raising an exception
signal.signal(signal.SIGALRM, master_timeout)

def receive_msg (read_queue, org):
    response = None
    response_str = None
    # When we've written to queue we read from agent response queue
    rmsgs = {}
    read_msgs={}
   
    # Receive at least 1 message be fore continuing 
    while ( len(rmsgs) == 0 ):
        rmsgs = read_queue.get_messages(num_messages=10, visibility_timeout=10)
        time.sleep(1)

    # For each message we check for duplicate, and if it is a response to our org message
    for rmsg in rmsgs:
   
        # Avoid duplicates 
        if rmsg.id in read_msgs:
            print 'Message has already been received'
            continue
        else:
            read_msgs[rmsg.id] = rmsg.id

        response=json.loads(rmsg.get_body())
        output = response['output']
        msg_id = str(response['msg_id'])
        type = str(response['type'])

        # Is it a response to our original request
        if msg_id != org.id:
            continue
   
        # Delete the message as quickly as possible 
        if not read_queue.delete_message(rmsg):
            print 'Failed to delete reponse message'
    
        if type == 'discovery':
            NOW = time.time()
            output = float(output)
            response_time = round(( NOW - output ), 2)
            response_str = 'Response time: ' + str(response_time) + ' seconds'
        elif type == 'cli':
            response_str =  output
        else:
            response_str = 'Unknown type response from agent ' + type

    return response_str

def delete_org_message (write_queue, org):
    # Pick up written message and delete it
    wmsgs = write_queue.get_messages(num_messages=10, visibility_timeout=10)
    
    for wmsg in wmsgs:
    
        if wmsg.id == org.id:
            if not write_queue.delete_message(wmsg):
                print 'Failed to original reponse message'
            return True
        else:
            return False

    return False


def run():

    #my_dict={'type': 'cli', 'when':'now', 'cmd':'uptime', 'ts':NOW};
    my_dict={'type': 'discovery', 'when':'now', 'cmd':'ping', 'ts':time.time()};
    STRING=json.dumps(my_dict)
    
    # Connect with key, secret and region
    conn = connect_to_region(REGION)
    write_queue = conn.get_queue(WRITE_QUEUE)
    read_queue = conn.get_queue(READ_QUEUE)
    
    # Write a messages
    message = write_queue.new_message(STRING)
    
    org = write_queue.write(message)
    if org.id is None:
        print 'Failed to write command to queue'
        exit
    
    # Start timeout
    signal.alarm(TIMEOUT)
    
    muh = None
    while ( muh is None ):
        muh = receive_msg (read_queue, org)
    print muh
    signal.alarm(0)
    
    signal.alarm(TIMEOUT)
    rm_org_msg = False
    while (rm_org_msg is False):
        rm_org_msg = delete_org_message (write_queue, org)
    signal.alarm(0)

if __name__ == "__main__":
    sys.exit(main())
