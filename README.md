### Salt Master Configuration

Currently, we only support Fedora 23.

#### Bootstrapping a Minion

Run:

```bash
curl radia.run | bash -s salt <master>
```

This will load the development version of Salt on the minion. There
are too many bugs in previous versions.

#### Installing the Master

The docker instance [is configured here](https://github.com/radiasoft/containers/tree/master/radiasoft/salt-master).

There is no automatic installer. The configuration lives in a
private repo for now. We'll eventually configure the master
from this repo.

#### Organization

This Salt repository is organized differently from others. All the
configuration, including which state trees to load, is driven off
pillars, using
[pillar.stack](https://github.com/saltstack/salt/blob/develop/salt/pillar/stack.py).

Each machine (minion) is described as a "system", which is a
complete list of what is installed. You should therefore start
with the
[systems directory](srv/pillar/systems). The minions directory
contains a symlink per "minion_id", which links to
one fo the `../systems/<type>-<channel>.cfg` files.

A systems file is a top level `pillar.stack` configuration,
which is a list of file names, relative to `/srv/pillar`.
Here's what `systems/jupyterhub-dev.cfg` looks like:

```text
channel/dev.yml
bivio.yml
jupyterhub/base.yml
jupyterhub/secret-slug-dev.yml
```

The first entry classifies the system according to its channel
(development pipeline stage). The next line configures the basic
bivio pillar configuration. The subsequent lines describe aspects
of the system. In this case, we configure the dev box
with the jupyterhub subsystem.

The last line is a slug for the secret file,
which isn't checked in for alpha, beta, or prod, as they
may be publicly accessible. It's convenient to have default
secret configuration so we provide host in `secret-slug` files.

#### State Tree Selectors

Every subsystem contains a pillar of the form:

```yaml
bivio:
  state_trees:
    jupyterhub:
      include: True
      require:
        - utilities
```

This is a state tree selector. Normally, states are configured in
Salt, but this is inconvenient for large subsystems. Rather, we
configure which subsystems are used, and what their dependencies are.

In this example, the `jupyterhub` state tree will be run.
It requires `utilities`, which is another state tree, which
must be run first.

You can selectively control whether subsystems are included
by modifying the `include` attribute of the subsystem. This
can be useful.

#### srv/salt/top.sls

The [top file](srv/salt/top.sls)
looks for the `bivio:state_trees` pillar, and
sorts the dependencies using a toposort. It then returns
the list of state trees to be execute by salt for this
minion.

#### srv/salt/_states/bivio.py

All states go through `bivio.py`, which defines a set of
higher level abstractions based on Bivio's policies. This
simplifies the state tree by consolidating dependencies.
For example, most system services are configured with
docker containers so the state `bivio.docker_container`
encapsulates the entire process of pulling the image,
configuring the container, and managing the systemd
service.

The other problem which `bivio.py` solves is to
document what is actually installed on the system,
not just what is described by the current salt
state trees and pillars. All bivio states document
their actions in files in `/var/lib/bivio-salt/inventory`
on the minion. Eventually, the inventory will contain
all actions to undo the actual state of the system.

#### Development

#### Master

Vagrantfile for the master:

```ruby
Vagrant.configure(2) do |config|
  config.vm.box = "fedora-23"
  config.vm.hostname = 'v1'
  config.vm.network "private_network", ip: "10.10.10.10"
  config.vm.synced_folder ".", "/vagrant", type: "virtualbox", disabled: true
  config.vbguest.auto_update = false
end
```

I work right out of `/srv`. As root install the master:

```bash
# See ~/src/radiasoft/containers/radiasoft/salt-master/build.sh
curl salt.run | bash -s -- -P -M -X -N -d -Z -n git develop
mkdir -p /var/{log,cache}/salt /srv
chown -R vagrant:vagrant /etc/salt /var/{log,cache}/salt /srv
```

As vagrant:

```bash
cd /srv
git clone https://github.com/biviosoftware/salt-conf
mv salt-conf/{.??*,*} .
rmdir salt-conf
ln -s srv/salt srv/pillar .
rm /etc/salt/master
ln -s /srv/etc/master /etc/salt
cat <<'EOF' > /etc/salt/master.d/vagrant.conf
pidfile: /tmp/salt-master.pid
log_level: debug
log_level_logfile: debug
EOF
ln -s ../systems/jupyterhub-dev.cfg /srv/srv/pillar/minions/v3
```

Start the master in an emacs window:

```bash
salt-master -l debug
```

#### Minion

Vagrantfile for the minion:

```ruby
Vagrant.configure(2) do |config|
  config.vm.box = "fedora-23"
  config.vm.hostname = 'v3'
  config.vm.network "private_network", ip: "10.10.10.30"
  config.vm.synced_folder ".", "/vagrant", type: "virtualbox", disabled: true
  config.vbguest.auto_update = false
end
```

Installing:

```bash
curl radia.run | bash -s salt 10.10.10.10
```

Then on the master:

```bash
salt-key -y -a v3
salt v3 state.apply
# This will restart the minion b/c salt config changed, then again with
# a long timeout, because this pulls the initial docker images:
salt v3 --timeout=300 state.apply
```

To reinstall the minion, you'll need to delete the key before the curl install:

```bash
salt-key -y -d v3
```


Executing on the minion gives more information, as root:

```bash
salt-call -l debug state.apply 2>&1 | tee err
```

#### References

[General discussion in Utilities Wiki.](https://github.com/biviosoftware/utilities/wiki/Salt)
