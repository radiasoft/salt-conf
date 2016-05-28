#!/bin/bash
#
# Starts sshd
#
set -e
cd $(dirname "$0")
exec /usr/sbin/sshd -D -f sshd_config
