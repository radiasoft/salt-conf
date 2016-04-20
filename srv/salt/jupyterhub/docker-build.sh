#!/bin/bash
{% from "jupyterhub/init.sls" import zz with context %}
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
    # Need to have this, due to ONBUILD image
    # https://github.com/jupyterhub/jupyterhub/issues/491
    touch jupyterhub_config.py
    cat >> build <<EOF
user={{ pillar.jupyterhub.admin_user }}
id=$(id -u {{ pillar.jupyterhub.admin_user }})
groupadd -g "$id" "$user"
useradd -m -s /bin/bash -g "$user" -u "$id" "$user"
echo "$user:{{ pillar.jupyterhub.admin_passwd }}" | chpasswd -e
# Do we need this? oauthenticator
pip3 install 'ipython[notebook]'
rm -rf ~/.cache
cd /
rm -rf /build
EOF
    cat >> Dockerfile <<'EOF'
FROM jupyter/jupyterhub
ADD . /build
RUN /build/build
EOF
    tag=jupyter:$(date -u +%Y%m%d.%H%M%S)
    docker build -t jupyterhub .
    docker tag jupyterhub:latest "$tag"
    docker tag -f jupyterhub:latest "jupyter:{{ pillar.pykern_pkconfig_channel }}"
) 1>&2
if (( $? )); then
    exit 1
fi
echo "changed=yes comment='Build: $tag; {{ pillar.pykern_pkconfig_channel }}'"
