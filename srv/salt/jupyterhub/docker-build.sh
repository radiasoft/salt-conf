#!/bin/bash
tag=jupyter:$(date -u +%Y%m%d.%H%M%S)
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
pip3 install 'ipython[notebook]'
pip3 install git+git://github.com/jupyter/oauthenticator.git
rm -rf ~/.cache
cd /
rm -rf /build
EOF
    cat >> Dockerfile <<'EOF'
FROM jupyter/jupyterhub
COPY . /build
RUN ["bash", "/build/build"]
EOF
    docker build -t jupyterhub .
    docker tag jupyterhub:latest "$tag"
    docker tag -f jupyterhub:latest "jupyter:{{ pillar.pykern_pkconfig_channel }}"
) 1>&2
if (( $? )); then
    exit 1
fi
echo "changed=yes comment='Build: $tag; {{ pillar.pykern_pkconfig_channel }}'"
