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
radia.yml
jupyterhub/base.yml
jupyterhub/secret-slug-dev.yml
```

The first entry classifies the system according to its channel
(development pipeline stage). The next line configures the basic
radia pillar configuration. The subsequent lines describe aspects
of the system. In this case, we configure the dev box
with the jupyterhub subsystem.

The last line is a slug for the secret file,
which isn't checked in for alpha, beta, or prod, as they
may be publicly accessible. It's convenient to have default
secret configuration so we provide host in `secret-slug` files.

#### State Tree Selectors

Every subsystem contains a pillar of the form:

```yaml
radia:
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
looks for the `radia:state_trees` pillar, and
sorts the dependencies using a toposort. It then returns
the list of state trees to be execute by salt for this
minion.

#### srv/salt/_states/radia.py

All states go through `radia.py`, which defines a set of
higher level abstractions based on our policies. This
simplifies the state tree by consolidating dependencies.
For example, most system services are configured with
docker containers so the state `radia.docker_container`
encapsulates the entire process of pulling the image,
configuring the container, and managing the systemd
service.

The other problem which `radia.py` solves is to
document what is actually installed on the system,
not just what is described by the current salt
state trees and pillars. All radia states document
their actions in files in `/var/lib/radia-salt/inventory`
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

Once logged in, start the master:

```bash
mkdir -p ~/src/radiasoft
cd ~/src/radiasoft
git clone https://github.com/radiasoft/salt-conf
cd salt-conf
bash salt-master.sh
```

This will do a lot of things, mostly creating files in the `run`
subdirectory, but also setting up NFS on the master so we
can test NFS for JupyterHub.

You can clear the state by simply:

```bash
rm -rf run
bash salt-master.sh
```

The master is setup for autoaccept.

#### Minion

Vagrantfile for the minion:

```ruby
Vagrant.configure(2) do |config|
  config.vm.box = "fedora-23"
  config.vm.hostname = 'v3'
  config.vm.provider "virtualbox" do |v|
    # Need more memory than default to run certain ops, e.g. install nfs-utils
    v.memory = 2048
  end
  config.vm.network "private_network", ip: "10.10.10.30"
  config.vm.synced_folder ".", "/vagrant", type: "virtualbox", disabled: true
  config.vbguest.auto_update = false
end
```

Installing minion as root:

```bash
curl radia.run | sudo bash -s salt 10.10.10.10
logout
```

You need to logout of the minion host, because salt will need to update
the user id for vagrant.

On the master in the salt-conf directory:

```bash
salt -c run/etc/salt v3 state.apply
# This will restart the minion b/c salt config changed, then again with
# a long timeout, because this pulls the initial docker images:
salt -c run/etc/salt v3 --timeout=300 state.apply
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

[General discussion in Utilities Wiki.](https://github.com/radiasoftware/utilities/wiki/Salt)
