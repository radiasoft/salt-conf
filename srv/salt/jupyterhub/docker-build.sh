#!/bin/bash
set -e
export TMPDIR=/tmp/docker-build-$RANDOM
exit_trap() {
    cd /
    rm -rf "$TMPDIR"
}
trap exit_trap EXIT
mkdir "$TMPDIR"
cd "$TMPDIR"
cat >> build <<EOF
user={{ pillar.jupyterhub.admin_user }}
id=$(id -u {{ pillar.jupyterhub.admin_user }})
groupadd -g "$id" "$user"
useradd -m -s /bin/bash -g "$user" -u "$id" "$user"
echo "$user:{{ pillar.jupyterhub.admin_passwd }}" | chpasswd -e
pip3 install 'ipython[notebook]' oauthenticator
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
echo "changed=yes comment='Build: $tag; {{ pillar.pykern_pkconfig_channel }}'"
