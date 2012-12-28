EC2_Collective
======

An orchestration tool build on the ideas of MColletive but for the cloud by using AWS SQS as the queue service. 
The agent will execute arbitrary commands and supports message filtering based on facts from e.g. puppet and queue isolation.

Why is it cool
--------

- *Decentralized*
  With python, boto and an IAM user, you can command your servers from anywhere. You are not tied to a 'mamagement' server

- *No firewalll problems*
  All communication is through AWS SQS so there is no need to open for specific ports to/from your servers
  New servers in new security group will simply work

- *Arbitrary commands*
  Create you own scripts and wrappers to perform those actions you need to do on a regular basis. Stop caring about Ruby and write your stuff in your beloved bash interpreter

- *Facts*
  Use puppet facts from yaml files or populate your own files and have the agent read them. Read text files like puppet classes.txt and filter on all of it as facts

- *Queue isolation*
  Ever executed a command in production that was meant for test servers? EC2_Collective lets you to use different queues for your different environments


Requirements
--------
* AWS account
* Python > 2.6 < 3
* Boto >= 1.9b

Setup
--------

### AWS SQS queues

I recommend basing your queues on your given environments. E.g. queues for testing, staging and production. For each environment 3 queues are required. 

Create those 3 queues with a prefix e.g. :

- *testing_master* Write queue for publisher / read queue for subscriber

Default Visibility Timeout: 0 seconds

Message Retention Period: 1 minutes

Maximum Message Size: 64 KB

Receive Message Wait Time: 20 seconds

- *testing_agent* Write queue fro subscriber / read queu for publisher

Default Visibility Timeout: 0 seconds

Message Retention Period: 1 minutes

Maximum Message Size: 64 KB

Receive Message Wait Time: 0 seconds

- *testing_facts* Cheat queue to allow publisher to know how many replies to expect

Default Visibility Timeout: 0 seconds

Message Retention Period: 1 minutes

Maximum Message Size: 64 KB

Receive Message Wait Time: 0 seconds

Be sure to set the queue configuration accordingly or else ec2_collective will fail to work.

### AWS IAM users

Create a user for the agent with the following policy:

    {
      "Statement": [
        {
          "Action": [
            "sqs:ListQueues",
            "sqs:GetQueueAttributes"
          ],
          "Effect": "Allow",
          "Resource": [
            "arn:aws:sqs:*:*:*"
          ]
        },
        {
          "Action": [
            "sqs:GetQueueAttributes",
            "sqs:GetQueueUrl",
            "sqs:ListQueues",      
            "sqs:ChangeMessageVisibility",
            "sqs:ChangeMessageVisibilityBatch",
            "sqs:SendMessage",
            "sqs:SendMessageBatch"
          ],
          "Effect": "Allow",
          "Resource": [
            "arn:aws:sqs:*:*:*_agent",
            "arn:aws:sqs:*:*:*_facts"
          ]
        },
     {
          "Action": [
            "sqs:GetQueueAttributes",
            "sqs:GetQueueUrl",
            "sqs:ListQueues",
         "sqs:ReceiveMessage"
          ],
          "Effect": "Allow",
          "Resource": [
            "arn:aws:sqs:*:*:*_master"
          ]
        }
      ]
    }

Create a user for the master 'publisher' tool:

    {
      "Statement": [
        {
          "Action": [
            "sqs:ListQueues",
            "sqs:GetQueueAttributes"
          ],
          "Effect": "Allow",
          "Resource": [
            "arn:aws:sqs:*:*:*"
          ]
        },
        {
          "Action": [
             "sqs:*"
          ],
          "Effect": "Allow",
          "Resource": [
            "arn:aws:sqs:*:*:*_agent",
            "arn:aws:sqs:*:*:*_master",
            "arn:aws:sqs:*:*:*_facts"
          ]
        }
      ]
    }

Agent installation
-------

Perform the following steps on the servers you wish to orchestrate

- *cp ec2-cagent /usr/sbin/ec2-cagent && chmod +x /usr/sbin/ec2-cagent*
- *cp scripts/ec2-cagent-init /etc/init.d/ec2-cagent && chmod +x /etc/init.d/ec2-cagent*
- *cp scripts/ec2-cagent-logrotate /etc/logrotate.d/ec2-cagent*
- *mkdir /var/log/ec2_collective/*
- *mkdir /etc/ec2_collective*
- *cp conf/ec2-cagent.json /etc/ec2_collective*
- Add a /etc/boto.cfg including the AWS IAM credentials

Edit your /etc/boto.cfg to contain

    [Boto]
    http_socket_timeout = 30

Edit your ec2-cagent.json according to your queues and fact file locations.

    { 
        "general": {
            "log_level": "INFO",
            "timeout": 30,
            "sqs_poll_interval": 1,
            "done_queue_poll_interval": 0.1,
            "yaml_facts": true,
            "yaml_facts_path": "/etc/ec2_collective/facts.yaml,/var/lib/puppet/state/classes.txt",
            "yaml_facts_refresh": 30,
            "use_facts_queue": true
        },
        "aws": {
            "region": "eu-west-1",
            "sqs_read_queue": "testing_master",
            "sqs_write_queue": "testing_agent",
            "sqs_facts_queue": "testing_facts"
        }
    }

Master installation
-------
