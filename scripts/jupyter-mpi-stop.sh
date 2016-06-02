#!/bin/bash
#
# Start the cluster
#
master=$1
username=$2
force=$3
if [[ -z $username || -z $(dig +short "$master" 2>/dev/null) ]]; then
    if [[ -n $master ]]; then
        echo "$master: not found" 1>&2
    fi
    echo "usage: $0 master github-user [force]" 1>&2
    exit 1
fi
if [[ -n $force ]]; then
    if [[ $force != force ]]; then
        echo "$force: force argument must equal 'force'" 1>&2
        exit 1
    fi
    force=true
else
    force=false
fi

set -e
salt=( salt -c $PWD/run/etc/salt -l info )
"${salt[@]}" "$master" state.apply
"${salt[@]}" "$master" state.apply jupyter-mpi-stop pillar="{username: '$username', force: $force}"
