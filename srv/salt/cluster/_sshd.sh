#!/bin/bash
#
# Starts sshd
#
set -e
cd $(dirname "$0")
export RADIA_RUN='/usr/sbin/sshd -D -e -f sshd_config'
{{
