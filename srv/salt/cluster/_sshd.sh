#!/bin/bash
#
# Starts sshd
#
set -e
cd $(dirname "$0")
# mpi makes multiple connections so sshd has to run in daemon mode
if [[ -z $RADIA_DEBUG ]]; then
    /usr/sbin/sshd -f sshd_config
    sleep infinity
else
    # get output to log in non-daemon mode
    while true; do
        /usr/sbin/sshd -D -d -d -d -f sshd_config > sshd.log 2>&1
    done
fi
