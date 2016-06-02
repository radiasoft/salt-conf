#!/bin/bash
#
# Start the cluster
#
master=$1
username=$2
if [[ -z $username || -z $(dig +short "$master" 2>/dev/null) ]]; then
    if [[ -n $master ]]; then
        echo "$master: not found" 1>&2
    fi
    echo "usage: $0 master github-user" 1>&2
    exit 1
fi

set -e
salt=( salt -c $PWD/run/etc/salt -l info )
"${salt[@]}" \* state.apply
"${salt[@]}" "$master" state.apply jupyter-mpi-start pillar="{'username': '$username'}"
