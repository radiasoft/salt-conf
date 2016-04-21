#!/bin/bash
#
# Installs dockersock selinux module:
# https://github.com/dpw/selinux-dockersock
#
# To remove: semodule -r dockersock
#
m=dockersock
if semodule -l | grep -s -q "$m"; then
    # Silently exit so no changes
    exit 0
fi
(
    set -e
    export TMPDIR=/tmp/docker-build-$RANDOM
    exit_trap() {
        cd /
        rm -rf "$TMPDIR"
    }
    trap exit_trap EXIT
    mkdir "$TMPDIR"
    cd "$TMPDIR"
    cat > "$m.te" <<EOF
module $m 1.0;
require {
    type docker_var_run_t;
    type docker_t;
    type svirt_lxc_net_t;
    class sock_file write;
    class unix_stream_socket connectto;
}
allow svirt_lxc_net_t docker_t:unix_stream_socket connectto;
allow svirt_lxc_net_t docker_var_run_t:sock_file write;
EOF

    checkmodule -M -m "$m".te -o "$m".mod
    semodule_package -m "$m".mod -o "$m".pp
    semodule -i "$m".pp
) 1>&2
if (( $? )); then
    exit 1
fi
echo "changed=yes comment='installed $m module'"
