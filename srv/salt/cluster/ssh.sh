#!/bin/bash
#
set -e
if [[ -z $RADIA_DEBUG ]]; then
    exec {{ zz.ssh_cmd }} "$@"
else
    # Only necessary for debugging with logs
    set -e
    flag=$1
    shift
    host=$2
    shift
    # Set to strace if necessary
    strace=
    log='{{ zz.guest_conf_d }}/$host/ssh.log'
    echo "Executing: {{ zz.ssh_cmd }} ${cmd[*]} $*" >> "$log"
    exec {{ zz.ssh_cmd }} "$flag" "$host" $strace "$@" 2>&1 | tee -a "$log"
fi
echo "ERROR: {{ zz.ssh_cmd }} '$@'" 1>&2
exit 1
