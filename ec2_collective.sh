#!/bin/sh -e
### BEGIN INIT INFO
# Provides:          ec2_collective.sh
# Required-Start:    $local_fs $remote_fs $network
# Required-Stop:     $local_fs $remote_fs $network
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# X-Interactive:     true
# Short-Description: Start/stop ec2_collective agent
### END INIT INFO
#
# ec2_collective	This init.d script is used to start ec2_collective agent

ENV="env -i LANG=C PATH=/usr/local/bin:/usr/bin:/bin"

NAME=ec2_collective
EC2_COLLECTIVE=/usr/sbin/ec2_collective
PIDFILE=/var/run/ec2_collectived.pid
IS_ACTIVE=1

set -e
if ! [ -x $EC2_COLLECTIVE ] ; then
	echo "No ec2_collective installed"
	exit 0
fi

if [ -s $PIDFILE ]; then
	PID=$(cat $PIDFILE)
	if ps -p $PID > /dev/null 2>&1 ; then
		IS_ACTIVE=0
	else
		IS_ACTIVE=1
	fi
else
	if pgrep $NAME > /dev/null 2>&1; then
		IS_ACTIVE=0
		PID=$(pgrep $NAME | head 1)
	else
		IS_ACTIVE=1
	fi
fi

. /lib/lsb/init-functions

case $1 in
	start)
		if [ ${IS_ACTIVE} -eq 0 ]; then
			log_warning_msg "ec2_collective is already running..."
                        log_end_msg 1
		else
			log_daemon_msg "Starting web server" "apache2"
                        log_end_msg 0

		fi
	;;
	stop)
		if [ ${IS_ACTIVE} -eq 0 ]; then
			log_daemon_msg "Stopping ec2_collective"
			kill $PID
                        log_end_msg 0
		else
			log_warning_msg "ec2_collective is already stopped..."
                        log_end_msg 1
		fi
	;;
	restart)
		log_daemon_msg 'Restarting ec2_collective'
		stop
		start
	;;
	status)
		if [ "$IS_ACTIVE" -eq 0 ]; then
			echo "Ec2_collective is running"
			exit 0
		else
			echo "Ec2_collective is NOT running."
			exit 1
		fi
	;;
	*)
		log_success_msg "Usage: /etc/init.d/ec2_collective {start|stop|restart|status}"
		exit 1
	;;
esac
