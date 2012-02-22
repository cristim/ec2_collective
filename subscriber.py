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

CFILE='./agent.json'

def get_yaml_facts (yaml_file):
    dataMap = {}

    if not os.path.exists(yaml_file):
        print yaml_file + ' file does not exist'
        sys.exit(1)

    stat = os.stat(yaml_file)
    fileage = int(stat.st_mtime)

    f = open(yaml_file, 'r')
    dataMap = yaml.safe_load(f)
    f.close()

    if len(dataMap) > 0:
        return (fileage, dataMap)
    else:
	return (fileage, None)

def update_yaml_facts (yf_last_update, yaml_file, yaml_facts):

    # Get file info
    stat = os.stat(yaml_file)
    fileage = int(stat.st_mtime)

    if fileage != yf_last_update:
	yf_last_update, dataMap = get_yaml_facts(yaml_file)
	return (fileage, dataMap)
    else:
	return (fileage, yaml_facts)

def cli_func (message, msg):

	try:
           o = subprocess.Popen(message['cmd'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
           output = o.communicate()[0]
           rc = o.poll()

        except OSError, e:
            output = ('Failed to execute ' + message['cmd'] + ' (%d) %s \n' % (e.errno, e.strerror))
            rc = e.errno 

        response={'func': message['func'], 'output': output, 'rc': rc, 'ts':time.time(), 'msg_id':msg.id, 'hostname':gethostname()};
        return response

def receive_msg ( read_msgs, read_queue, yaml_facts ):

    response = None

    msgs = read_queue.get_messages(num_messages=10, visibility_timeout=0)

    for msg in msgs:

	if msg.id in read_msgs:
            continue
        else:
            read_msgs[msg.id] = msg.id
   
        message=json.loads(msg.get_body())
        cmd_str = str(message['cmd'])
        func = str(message['func'])
        ts = str(message['ts'])
        wf = message['wf']
        wof = message['wof']

	if fact_lookup(wf, wof, yaml_facts):
            read_msgs[msg.id] = msg.id
            continue
  
        if func in [ 'discovery', 'ping', 'count' ]:
            response={'func': func, 'output': ts, 'rc': '0', 'ts':time.time(), 'msg_id':msg.id, 'hostname':gethostname()};
        elif func == 'cli':
            response = cli_func (message, msg) 
        else:
           response =  'Unknown command ' + cmd_str
           response={'func': func, 'output': response, 'rc': '0', 'ts':time.time(), 'msg_id':msg.id, 'hostname':gethostname()};

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
    # CFILE 
    if not os.path.exists(CFILE):
        print CFILE + ' file does not exist'
        sys.exit(1)
    
    try:
        f = open(CFILE, 'r')
    except IOError, e:
        print ('Failed to execute ' + message['cmd'] + ' (%d) %s \n' % (e.errno, e.strerror))
    
    try:
        global CFG
        CFG=json.load(f)
    except (TypeError, ValueError), e:
        print 'Error in configuration file'
        sys.exit(1)

def daemonize (stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    try:
        pid = os.fork( )
        if pid > 0:
            sys.exit(0) # Exit first parent.
    except OSError, e:
        sys.stderr.write("fork #1 failed: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)
    # Decouple from parent environment.
    os.chdir("/")
    os.umask(0)
    os.setsid( )
    # Perform second fork.
    try:
        pid = os.fork( )
        if pid > 0:
            sys.exit(0) # Exit second parent.
    except OSError, e:
        sys.stderr.write("fork #2 failed: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)
    # The process is now daemonized, redirect standard file descriptors.
    for f in sys.stdout, sys.stderr: f.flush( )
    si = file(stdin, 'r')
    so = file(stdout, 'a+')
    se = file(stderr, 'a+', 0)
    os.dup2(si.fileno( ), sys.stdin.fileno( ))
    os.dup2(so.fileno( ), sys.stdout.fileno( ))
    os.dup2(se.fileno( ), sys.stderr.fileno( ))

def fact_lookup (wf, wof, yaml_facts):
    # WOF
    # Return True if we have the fact ( just on should skip message )
    # Return False if we don't have the fact

    # WF
    # Return False if we have all the fact ( all facts must match )
    # Return True if we don't have the fact

    # If nothing is set we process message
    if wf is None and wof is None:
        return False

    # If wof is in facts we return True ( skip message )
    if wof is not None:
        wof = wof.split(',')
        for f in wof:
            if '=' in f:
                f = f.split('=')
    
                if (f[0] in yaml_facts) and (yaml_facts[f[0]] == f[1]):
                    return True
            else:
                if f in yaml_facts:
    		    return True

    # Without is set but we did not find it, if wf is not set we return False ( process message )
    if wf is None:
        return False

    # If all wf is in facts we return False ( process message )
    no_match=0
    wf = wf.split(',')
    for f in wf:
        if '=' in f:
            f = f.split('=')
   
            if (f[0] not in yaml_facts) or (yaml_facts[f[0]] != f[1]):
                no_match += 1
        else:
            if f not in yaml_facts:
                no_match += 1

    if no_match == 0 :
        # All facts was found ( process message )
        return False
    else:
        # Facts set was not found - return True ( skip message )
        return True

def main ():

    get_config()

    sys.stdout.write('Daemon started with pid %d\n' % os.getpid( ) )
    sys.stdout.write('Daemon stdout output\n')
    sys.stderr.write('Daemon stderr output\n')

    # Get facts
    if CFG['general']['yaml_facts'] == 'True':
        yf_last_update, yaml_facts = get_yaml_facts(CFG['general']['yaml_facts_path'])
    else:
        yaml_facts = None

    # Connect with key, secret and region
    conn = connect_to_region(CFG['aws']['region'])
    read_queue = conn.get_queue(CFG['aws']['read_queue'])
    write_queue = conn.get_queue(CFG['aws']['write_queue'])
    
    # Read from master
    read_msgs={}
   
    start_time=int(time.time()) 
    last_read=time.time()
    response = False
    while ( True ):

        # See if we need to update facts file
        if (int(time.time()) - start_time ) > CFG['general']['yaml_facts_refresh']:
	    start_time=time.time()
	    yf_last_update, yaml_facts = update_yaml_facts(yf_last_update, CFG['general']['yaml_facts_path'], yaml_facts )

        # Do not poll SQS too often, that would be too expensive
        if (time.time() - last_read) > CFG['general']['sqs_poll_interval']:
            read_msgs, response = receive_msg ( read_msgs, read_queue, yaml_facts )
            last_read=time.time()
        else:
           time.sleep(0.5) 

        if response:
            write_msg (response, write_queue)

if __name__ == "__main__":
    daemonize('/dev/null','/tmp/daemon.log','/tmp/daemon.log')
    sys.exit(main())
