#!/bin/bash
set -e
export PATH="{{ zz.guest_d }}:$PATH"
exec mpiexec --hostfile '{{ zz.hosts_f }}' "$@"
