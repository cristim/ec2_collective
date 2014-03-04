#!/usr/bin/env python
# coding: utf-8

from boto.sqs import connect_to_region


REGION='eu-west-1'
WRITE_QUEUE='testing_master'
READ_QUEUE='testing_agent'

# Connect with key, secret and region
conn = connect_to_region(REGION)
write_queue = conn.get_queue(WRITE_QUEUE)
read_queue = conn.get_queue(READ_QUEUE)
read_queue.clear()
write_queue.clear()
