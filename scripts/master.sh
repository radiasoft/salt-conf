#!/bin/bash
#
# start salt-master for dev
#
set -e

: ${master_ip:=10.10.10.10}
: ${jupyterhub_minion_id:=z30.bivio.biz}
: ${mpi_minion_id:=z40.bivio.biz}

cd "$(dirname $0)/.."

if ! ip addr show eth1 | grep -s -q "$master_ip"; then
    echo "Call with master_ip=a.b.c.d bash $0" 1>&2
    exit 1
fi

jupyterhub_ip=$(dig +short "$jupyterhub_minion_id")

_create() {
    local file=$1
    local force=$2
    if [[ -z $force && -r $file ]]; then
        return
    fi
    dd of="$file"
    return
}

_link() {
    local src=$1
    local dest=$2
    if [[ -L $dest ]]; then
        return
    fi
    ln -s "$src" "$dest"
    return
}

_sudo_append() {
    local file=$1
    local line=$2
    if grep -s -q "$line" "$file"; then
        return 1
    fi
    echo "$line" | sudo dd of="$file" oflag=append
    return
}

#
# Config and directories
#
root_dir=$PWD/run
nfs_d=$root_dir/nfs
nfs_local_d=/var/nfs/jupyter
salt_d=$root_dir/srv/salt
minion_conf=99-radia-dev.conf
mkdir -p $root_dir/{etc/salt/{master.d,pki},var/cache/salt,var/log/salt,var/run/salt,secrets} \
      "$nfs_d" "$salt_d"
sudo exportfs -u -v "*:$nfs_d" || true
sudo chown vagrant:vagrant "$nfs_d"
sudo chmod 755 "$nfs_d"

#
# Global actions
#
if [[ -z $(type -t salt-master) ]]; then
    echo "Installing salt-master..." 1>&2
    curl salt.run | bash -s -- -P -M -X -N -d -Z -n git develop
fi
# Need no_root_squash, b/c $PWD is not accessible by root
if _sudo_append /etc/hosts.allow 'rpcbind portmap lockd statd mountd rquotad: ALL' \
    || _sudo_append /etc/exports "$nfs_d *(rw,no_root_squash,sync)"; then
    sudo systemctl restart nfs
fi
# Always export
sudo exportfs -av

bash scripts/docker-tls.sh "$mpi_minion_id"

#
# Local config. Redo by removing run directory:
#
#   rm -rf run
#
_link ../../../etc/master "$root_dir/etc/salt/master"
# can't use run/srv/pillar, b/c cfg files are relative to the file
# they are imported from so doesn't act like salt file server
_link ../systems/jupyterhub-dev.cfg "srv/pillar/minions/$jupyterhub_minion_id.cfg"
_link ../systems/jupyterhub-mpi-dev.cfg "srv/pillar/minions/$mpi_minion_id.cfg"

_create run/etc/salt/master.d/99-dev.conf <<EOF
auto_accept: true
file_roots:
  base:
    - "$PWD/srv/salt"
    - "$salt_d"
ext_pillar:
  - stack: "$PWD/srv/pillar/top.cfg"
log_level: debug
log_level_logfile: quiet
root_dir: "$root_dir"
user: "$USER"
EOF

_create srv/pillar/secrets/radia-dev.yml force <<EOF
radia:
  minion_update:
    config_source:
      - 'salt://$minion_conf'
EOF

_create srv/pillar/secrets/jupyter-dev.yml force <<EOF
jupyter:
  nfs_local_d: "$nfs_local_d"
  nfs_remote_d: "$master_ip:$nfs_d"
  root_notebook_d: "$nfs_local_d"
EOF

_create srv/pillar/secrets/jupyterhub-dev.yml force <<EOF
jupyterhub:
  admin_users:
  - vagrant
  authenticator_class: jupyterhub.auth.PAMAuthenticator
  aux_contents: |
    import subprocess
    subprocess.check_call('echo vagrant:vagrant|chpasswd', shell=True)
  cookie_secret: 'qBdGBamOJTk5REgm7GUdsReB4utbp4g+vBja0SwY2IQojyCxA+CwzOV5dTyPJWvK13s61Yie0c/WDUfy8HtU2w=='
  db_pass: Ydt21HRKO7NnMBIC
  github_client_id: ignored
  github_client_secret: ignored
  proxy_auth_token: '+UFr+ALeDDPR4jg0WNX+hgaF0EV5FNat1A3Sv0swbrg='

postgresql_jupyterhub:
  admin_pass: 2euhoxplPzleKWLZ
EOF

_create srv/pillar/secrets/cluster-dev.yml force <<EOF
radia:
  cluster_start:
    username: vagrant
    host_root_d:
    hosts: [ $mpi_minion_id ]

EOF


_create "$salt_d/$minion_conf" <<EOF
log_level: debug
log_level_logfile: debug
EOF

#
# Start salt-master
#
echo "root_dir: $root_dir" 1>&2
exec salt-master -l debug -c "$root_dir/etc/salt"
