#!/usr/bin/env python

from boto.sqs.connection import SQSConnection
from boto.sqs.regioninfo import SQSRegionInfo
from boto.sqs import connect_to_region
from socket import gethostname
import simplejson as json
import subprocess, shlex, time

REGION='eu-west-1'
READ_QUEUE='master'
WRITE_QUEUE='agent'
HOSTNAME=gethostname()

# Connect with key, secret and region
conn = connect_to_region(REGION)
read_queue = conn.get_queue(READ_QUEUE)
write_queue = conn.get_queue(WRITE_QUEUE)

def cli_func (message, msg):

	try:
           o = subprocess.Popen(message['cmd'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
           output = o.communicate()[0]
           rc = o.poll()

        except OSError, e:
            output = ('Failed to execute ' + message['cmd'] + ' (%d) %s \n' % (e.errno, e.strerror))
            rc = e.errno 

        response={'type': message['type'], 'output': output, 'rc': rc, 'ts':NOW, 'msg_id':msg.id, 'hostname':HOSTNAME};
        return response

def receive_msg (msgs, read_msgs ):


    for msg in msgs:

	if msg.id in read_msgs:
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
  
        if type == 'discovery' or type== 'ping':
            response={'type': type, 'output': ts, 'rc': '0', 'ts':NOW, 'msg_id':msg.id, 'hostname':HOSTNAME};
        elif type == 'count':
            response={'type': type, 'output': 'yes master?', 'rc': '0' , 'ts': time.time(), 'msg_id':msg.id, 'hostname':HOSTNAME};
        elif type == 'cli':
            response = cli_func (message, msg) 
        else:
           response =  'Unknown command ' + cmd_str
           response={'type': type, 'output': response, 'rc': '0', 'ts':NOW, 'msg_id':msg.id, 'hostname':HOSTNAME};
 
        response=json.dumps(response)
        message = write_queue.new_message(response)

        # Write message 5 times to make sure receiver gets it
        written='no'
        for i in range(0, 3):
            org = write_queue.write(message)
            if org.id is None and written == 'no':
                print 'Failed to write response message'
                del read_msgs[msg.id]
            else:
                written='yes'
    
    return read_msgs

# Read from master
read_msgs={}

while True:
    NOW = time.time()
    msgs = read_queue.get_messages(num_messages=10, visibility_timeout=0)

    if (len(msgs) > 0):
        read_msgs = receive_msg ( msgs, read_msgs )
