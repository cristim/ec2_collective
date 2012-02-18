#!/usr/bin/env python

from boto.sqs.connection import SQSConnection
from boto.sqs.regioninfo import SQSRegionInfo
from boto.sqs import connect_to_region
import simplejson as json
import subprocess, shlex, time

REGION='eu-west-1'
READ_QUEUE='master'
WRITE_QUEUE='agent'

# Connect with key, secret and region
conn = connect_to_region(REGION)
read_queue = conn.get_queue(READ_QUEUE)
write_queue = conn.get_queue(WRITE_QUEUE)

def cli_func (message):

        cmd_w_args = shlex.split(message['cmd'])

	try:
           response = subprocess.Popen(cmd_w_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]

        except OSError:
           response =  'Failed to execute ' + cmd_str

        print 'Our response is ' + response
        response={'type': type, 'output': response, 'ts':NOW, 'msg_id':msg.id};
        return response

def receive_msg (msgs, read_msgs ):

    print 'Message received'

    for msg in msgs:

	if msg.id in read_msgs:
            print 'Old message received - skipping'
            continue
        else:
            read_msgs[msg.id] = msg.id
   
        #print "Message ID: ",msg.id
        #print "Message Handle: ",msg.receipt_handle
        #print "Queue ID: ", msg.queue.id
        #print "Message Body: ", msg.get_body()
     # 
        message=json.loads(msg.get_body())
        cmd_str = str(message['cmd'])
        type = str(message['type'])
        ts = str(message['ts'])
  
        if type == 'discovery':
            response={'type': type, 'output': ts, 'ts':NOW, 'msg_id':msg.id};
        elif type == 'cli':
            response = cli_func (message) 
        else:
           response =  'Unknown command ' + cmd_str
           response={'type': type, 'output': response, 'ts':NOW, 'msg_id':msg.id};
 
        response=json.dumps(response)
        message = write_queue.new_message(response)
        write_queue.write(message)
        print 'Responded to message'
    
    return read_msgs

# Read from master
read_msgs={}

while True:
    NOW = time.time()
    msgs = read_queue.get_messages(num_messages=10, visibility_timeout=0)

    if (len(msgs) > 0):
        read_msgs = receive_msg ( msgs, read_msgs )
