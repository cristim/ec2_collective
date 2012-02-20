#!/usr/bin/env python
# coding: utf-8

from boto.sqs.connection import SQSConnection
from boto.sqs.regioninfo import SQSRegionInfo
from boto.sqs import connect_to_region
from socket import gethostname
import simplejson as json
import subprocess, time
import time
import sys
import yaml
import os

CFG='./agent.json'

def cli_func (message, msg):

	try:
           o = subprocess.Popen(message['cmd'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
           output = o.communicate()[0]
           rc = o.poll()

        except OSError, e:
            output = ('Failed to execute ' + message['cmd'] + ' (%d) %s \n' % (e.errno, e.strerror))
            rc = e.errno 

        response={'type': message['type'], 'output': output, 'rc': rc, 'ts':time.time(), 'msg_id':msg.id, 'hostname':gethostname()};
        return response

def receive_msg ( read_msgs, read_queue ):

    response = None

    msgs = read_queue.get_messages(num_messages=10, visibility_timeout=0)

    for msg in msgs:

	if msg.id in read_msgs:
            continue
        else:
            read_msgs[msg.id] = msg.id
   
        message=json.loads(msg.get_body())
        cmd_str = str(message['cmd'])
        type = str(message['type'])
        ts = str(message['ts'])
  
        if type in [ 'discovery', 'ping', 'count' ]:
            response={'type': type, 'output': ts, 'rc': '0', 'ts':time.time(), 'msg_id':msg.id, 'hostname':gethostname()};
        elif type == 'cli':
            response = cli_func (message, msg) 
        else:
           response =  'Unknown command ' + cmd_str
           response={'type': type, 'output': response, 'rc': '0', 'ts':time.time(), 'msg_id':msg.id, 'hostname':gethostname()};

    return read_msgs, response

def write_msg (response, write_queue):
 
    response=json.dumps(response)
    message = write_queue.new_message(response)
    
    # Write message 5 times to make sure receiver gets it
    written=False
    for i in range(0, 3):
        org = write_queue.write(message)
        if org.id is None and written is False:
            print 'Failed to write response message'
            del read_msgs[msg.id]
        else:
            written=True

    return written

def get_config():
    # CFG FILE
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

def main():
    # FORK

    run()

def run ():

    get_config()

    # Connect with key, secret and region
    conn = connect_to_region(CONFIG['aws']['region'])
    read_queue = conn.get_queue(CONFIG['aws']['read_queue'])
    write_queue = conn.get_queue(CONFIG['aws']['write_queue'])
    
    # Read from master
    read_msgs={}
    
    while ( True ):
        read_msgs, response = receive_msg ( read_msgs, read_queue )
        if response:
            write_msg (response, write_queue)

if __name__ == "__main__":
    sys.exit(main())
