#!/bin/bash
set -e
export PATH="{{ zz.guest_conf_d }}:$PATH"
exec mpiexec -output-filename '{{ zz.guest_output_d }}' -hostfile '{{ zz.hosts_f }}' bash '{{ zz.user_sh }}'
