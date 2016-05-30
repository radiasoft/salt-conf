#!/bin/bash
set -e
dash_x=
if [[ -n $RADIA_DEBUG ]]; then
    set -x
    dash_x=-x
fi
export PATH="{{ zz.guest_conf_d }}:$PATH"
# See radiasoft/salt-conf#5. Can't have output files:
# -output-filename '{{ zz.guest_output_prefix }}'
# interfaces have to be excluded or you get errors
exec mpiexec  \
     --mca btl_tcp_if_include '{{ zz.mpi_subnet }}' \
     --mca oob_tcp_if_include '{{ zz.mpi_subnet }}' \
     -hostfile '{{ zz.guest_hosts_f }}' \
     bash $dash_x '{{ zz.guest_user_sh }}'
echo mpiexec failed 1>&2
