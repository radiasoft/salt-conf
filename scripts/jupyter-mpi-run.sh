#!/bin/bash
#
# Start the cluster
#
master=$1
username=$2
if [[ -z $username || -z $(dig +short "$master" 2>/dev/null) ]]; then
    echo "usage: $0 $master github-user" 1>&2
    exit 1
fi

set -e
salt=( salt -c $PWD/run/etc/salt -l info $master )
"${salt[@]}" saltutil.sync_all
"${salt[@]}" saltutil.refresh_pillar
"${salt[@]}" state.apply jupyter-mpi-run pillar="{'username': '$username'}"
