#!/bin/bash
#
# run salt command
#
cd "$(dirname $0)/.."
root_dir=$PWD/run
exec salt -c "$root_dir/etc/salt" "$@"
