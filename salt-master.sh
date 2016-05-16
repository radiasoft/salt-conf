#!/bin/bash
#
#
cd "$(dirname "$0")"
if [[ -z $(type -t salt-master) ]]; then
    echo "Installing salt-master..." 1>&2
    curl salt.run | bash -s -- -P -M -X -N -d -Z -n git develop
fi
echo "Starting salt-master: $PWD" 1>&2
mkdir -p run/{etc/salt/{master.d,pki},var/cache/salt,var/log/salt,run/salt}
if [[ ! -L run/etc/salt/master ]]; then
    ln -s ../../../etc/master run/etc/salt/master
if
if [[ ! -L run/srv ]]; then
    ln -s ../../srv run/srv
if
if [[ ! -r run/etc/salt/master.d/bivio-vagrant.conf ]]; then
    cat > run/etc/salt/master.d/bivio-vagrant.conf <<"EOF"
auto_accept: true
base:
  - "$PWD/srv/salt"
log_level: debug
log_level_logfile: quiet
pillar_roots:
  base:
  - "$PWD/srv/pillar"
root_dir: "$PWD/run"
user: $USER
EOF
fi
exec salt-master -c "$PWD/run/etc/salt"
