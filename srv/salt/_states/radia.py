# -*- coding: utf-8 -*-
"""

* Do not rely on 'name', be explicit: service_name, image_name, etc.
* Defaults are in pillar by same name as state, all are overwriteable by args
* Reuse flags like dir_mode, makedirs.
* Avoid setting values in states that can't be overriden by pillars
* Do not use files unless absolutely necessary. You can't override files or states,
  but you can override pillars with more qualified config.
* "ret" is checked before operations, e.g. call_state, so that if there's
  an error, it won't execute. Makes it easier to chain commands.
"""
from __future__ import absolute_import, division, print_function

import collections
import contextlib
import copy
import datetime
import glob
import inspect
import logging
import os
import os.path
import pwd
import re
import salt.utils
import socket
import subprocess
import tempfile
import time
import yaml

radia = None

_initialized = False

_saved_returns = {}

_IPV4_ADDR = re.compile(r'^((?:\d+\.)+)(\d+)$')

# Very conservative unquoted shell command argument
_SHELL_SAFE_ARG = re.compile(r'^[-_/:\.\+,a-zA-Z0-9]+$')

_DOCKER_FLAG_PAIRS = {
    'volumes': '-v',
    'ports': '-p',
    'links': '--link',
    'env': '-e',
}

_DOCKER_TLS_FLAGS = ('tlskey', 'tlscert', 'tlscacert')

'''
def docker_update():
    update and restart
    restart all containers
    need to know what order though
    containers

def pkg_update():
    need to udpate all known packages and reboot

'''

def cluster_start(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    if not _cluster_start_args(zz, ret)['result']:
        return ret
    _cluster_start_args_assert(zz, ret)
    if not ret['result']:
        return ret
    res = _sh(
        "docker inspect -f '{{ .State.Running }}' " + zz['master_container_name'],
        ret, ignore_errors=True, env=_docker_tls_env(zz, zz['mpi_master_host']))
    if 'true' in res:
        return _err(zz, ret, '{master_container_name}: master container is running, must stop first')
    _call_state(
        'plain_directory',
        {
            'name': zz['master_container_name'] + '.host_conf_d',
            'dir_name': zz['host_conf_d'],
        },
        ret,
    )
    with _chdir(zz['host_conf_d']):
        _cluster_config_master(zz, ret)
        for host in zz['hosts']:
            _cluster_config_host(zz, ret, host)
    _sh('chown -R {host_user}:{host_user} {host_conf_d}'.format(**zz), ret)
    _sh('chmod -R go= {host_conf_d}'.format(**zz), ret)
    return _cluster_start_containers(zz, ret)


def cluster_stop(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _pillar(zz, 'cluster_start')
    if not _cluster_start_args(zz, ret)['result']:
        return ret
    env = _docker_tls_env(zz, zz['mpi_master_host'])
    res = _sh(
        "docker inspect -f '{{ .State.Running }}' " +  zz['master_container_name'],
        ret, ignore_errors=True, env=env)
    # TODO(robnagler) verify result is one of expected: true or false or error in no such image else abort
    if 'true' in res and not ('force' in __pillar__ and  __pillar__['force']):
        return _err(zz, ret, '{master_container_name}: master container is running, must stop first, or pass "pillar={{force: true}}"')
    container = zz['master_container_name']
    for host in [zz['mpi_master_host']] + zz['hosts'].keys():
        _debug('host={}', host)
        env = _docker_tls_env(zz, host)
        _sh('env; docker rm -f {}'.format(container), ret, ignore_errors=True, env=env)
        res = _sh(
            "docker inspect -f '{{ .State.Running }}' " + container + ' 2>&1',
            ret, ignore_errors=True, env=env)
        if not re.search('error|false', res, flags=re.IGNORECASE):
            return _err(zz, ret, '{}: {} container did not stop; State.Running={}', host, container, res)
        container = zz['host_container_name']
    _sh('rm -rf {host_conf_d}'.format(**zz), ret, ignore_errors=True)
    if os.path.exists(zz['host_conf_d']):
        return _err(zz, ret, '{host_conf_d}: unable to remove')
    return ret


def docker_container(**kwargs):
    """Initiate a docker container as a systemd service."""
    # Needs to be set here for _caller() to be right
    zz, ret = _docker_container_args(kwargs)
    if not ret['result']:
        return _save_ret(zz, ret)
    _call_state('docker_image', {'name': zz['name'] + '.image', 'image_name': zz['image_name']}, ret)
    _call_state('docker_sock_semodule', {}, ret)
    _call_state(
        'plain_file',
        {
            'name': zz['service_name'] + '.systemd_file',
            'file_name': zz['systemd_filename'].format(**zz),
            'contents': zz['systemd_contents'],
            'user': 'root',
            'group': 'root',
            'zz': zz,
        },
        ret,
    )
    if zz['makedirs']:
        for v in zz['volumes']:
            _call_state(
                'plain_directory',
                {
                    'name': zz['container_name'] + '.directory.' + v[0],
                    'dir_name': v[0],
                },
                ret,
            )
    _docker_container_init(zz, ret)
    return _save_ret(zz, _service_restart(zz, ret))


def docker_image(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    i = _docker_image_name(zz['image_name'])
    exists, ret = _docker_image_exists(i, ret)
    if not ret['result']:
        return ret
    new = {}
    if exists and not zz.get('want_update', False):
        new['comment'] = 'image already pulled'
    else:
        env = zz.get('docker_env', None)
        res = _sh('docker pull {}'.format(i), ret, env=env)
        if not ret['result']:
            return ret
        if 'up to date' in res:
            new['comment'] = 'image is up to date'
        else:
            new['comment'] = 'image needed to be pulled'
            new['changes'] = {'new': 'docker pull ' + i}
    return _ret_merge(i, ret, new)


def docker_service(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _call_state('host_user', {}, ret)
    _docker_service_tls(zz, ret)
    if zz['disable_firewall']:
        _service_disable({'service_name': 'firewalld'}, ret)
    _call_state(
        'plain_file',
        {
            'name': 'docker_service.sysconfig',
            'file_name': '/etc/sysconfig/docker',
            'contents_pillar': 'radia:docker_service:sysconfig_contents',
            'user': 'root',
            'group': 'root',
            'zz': zz,
        },
        ret,
    )
    zz['service_name'] = 'docker'
    # Ignore incoming name as it doesn't matter for the rest
    if _service_status(zz)[0] and not ret['changes']:
        _ret_merge(zz, ret, {'comment': 'service is running'})
    else:
        _call_state('pkg_installed', {'name': 'docker_service.pkgs', 'pkgs': zz['required_pkgs']}, ret)
        if not ret['result']:
            return ret
        lvs = _sh('lvs', ret);
        # VirtualBox VMs don't have LVMs so we used the default loopback device
        # and don't need to setup storage. Fedora has "docker" in the
        # volume name.
        if lvs and 'docker' not in lvs:
            _sh('docker-storage-setup', ret)
        _service_restart(zz, ret)
    if ret['changes']:
        _sh('chgrp {sock_group} {sock}'.format(**zz), ret)
    return ret


def docker_sock_semodule(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    modules = _sh('semodule -l', ret)
    if not modules or zz['policy_name'] in modules:
        return ret
    with _temp_dir() as d:
        pn = zz['policy_name']
        _call_state(
            'plain_file',
            {
                'name': 'docker_sock_semodule.policy_template',
                'file_name': os.path.join(d, pn + '.te'),
                'contents': zz['contents'],
                'zz': zz,
            },
            ret,
        )
        # must be the name of the file
        for cmd in (
            'checkmodule -M -m {pn}.te -o {pn}.mod',
            'semodule_package -m {pn}.mod -o {pn}.pp',
            # will exit -9 (out of memory) when there is "only" 256MB of RAM
            'semodule -i {pn}.pp',
        ):
            _sh(cmd.format(pn=pn), ret)
    return ret


def docker_tls_client(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _assert_args(zz, ['cert_d'])
    _call_state(
        'plain_directory',
        {
            'name': 'docker_tls_client.cert_d',
            'dir_name': zz['cert_d'],
            'group': zz['group'],
            'user': zz['user'],
        },
        ret,
    )
    _assert_args(zz, _DOCKER_TLS_FLAGS)
    for k in _DOCKER_TLS_FLAGS:
        b = 'ca' if k == 'tlscacert' else k[3:]
        f = os.path.join(zz['cert_d'], b + '.pem')
        _call_state(
            'plain_file',
            {
                'name': 'docker_tls_client.' + k,
                'file_name': f,
                'contents': zz[k],
                'group': zz['group'],
                'user': zz['user'],
            },
            ret,
        )
    return ret


def file_append(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    zz['name'] = zz['file_name']
    # TypeError: append() got an unexpected keyword argument 'file_name'
    del zz['file_name']
    _call_state('file.append', zz, ret)
    return ret


def host_user(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _assert_name(zz['user'])
    _host_user_uid(zz, ret)
    _call_state('group.present', {'name': zz['user'], 'gid': zz['uid']}, ret)
    _call_state('group.present', {'name': zz['docker_group'], 'gid': zz['docker_gid']}, ret)
    _call_state(
        'user.present',
        {
            'name': zz['user'],
            'uid': zz['uid'],
            'gid': zz['uid'],
            'groups': [zz['docker_group']],
            'createhome': True,
        },
        ret,
    )
    return ret


def minion_update(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    for f in zz['config_source']:
        b = os.path.basename(f)
        _debug('{} => {}', f, os.path.join(zz['config_d'], b))
        _call_state(
            'plain_file',
            {
                'name': 'minion.config.' + b,
                'file_name': os.path.join(zz['config_d'], b),
                'source': f,
                'user': 'root',
                'group': 'root',
            },
            ret,
        )

    if not ret['result'] or not ret['changes']:
        return ret
    __salt__['service.restart'](name='salt-minion')
    return _ret_merge(
        zz,
        ret,
        {
            'result': False,
            'changes': {'new': 'salt-minion restarted'},
            'comment': '\n*** YOU NEED TO RERUN THIS STATE unless it is minion_update ****\n',
        },
    )


def mod_watch(**kwargs):
    _debug('kwargs={}', kwargs)
    if kwargs['sfun'] != 'docker_container':
        raise AssertionError(
            '{} radia.{}: cannot watch state "{}"'.format(
                kwargs['name'],
                kwargs['sfun'],
                kwargs['__reqs__']['watch'][0]['__id__'],
            ),
        )
    zz, ret = _docker_container_args(kwargs)
    # We don't want to clobber previous returns
    ret = _saved_returns[zz['name']]
    if ret['changes'].get(zz['service_name']):
        _debug('{}: already restarted', zz['service_name'])
    else:
        _service_restart(zz, ret, force=True)
    return _save_ret(zz, ret)


def nfs_export(**kwargs):
    #TODO: setsebool -P nfs_export_all_rw 1
    pass


def nfs_mount(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _call_state(
        'pkg_installed',
        {
            'name': 'nfs_mount.pkgs',
            'pkgs': ['nfs-utils'],
        },
        ret,
    )
    _call_state(
        'plain_directory',
        {
            'name': 'nfs_mount.' + zz['local_dir'],
            'dir_name': zz['local_dir'],
            'user': zz['user'],
            'group': zz['group'],
            'dir_mode': zz['dir_mode'],
        },
        ret,
    )
    _call_state(
        'file_append',
        {
            'file_name': zz['fstab'],
            'text': '{} {} nfs {}'.format(zz['remote_dir'], zz['local_dir'], zz['options']),
        },
        ret,
    )
    ret = _nfs_mount_selinux(zz, ret)
    if not ret['result']:
        return ret
    if zz['remote_dir'] in _sh('mount', ret):
        if not ret['result'] or not ret['changes']:
            return ret
        # This probably won't work, because the directories will be in use.
        # Need a global restart concept.
        _sh('umount {}'.format(zz['local_dir']), ret)
    _sh('mount {}'.format(zz['local_dir']), ret)
    return ret


def plain_directory(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    zz['name'] = zz['dir_name']
    _call_state('file.directory', zz, ret)
    return ret


def plain_file(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    zz['name'] = zz['file_name']
    op = 'managed'
    if zz.get('append', False):
        op = 'append'
        zz['text'] = zz['contents']
    ret = _ret_init(zz)
    zz['context'] = {'zz': copy.deepcopy(zz)}
    if 'zz' in zz:
        zz['context']['zz'].update(zz['zz'])
    _call_state('file.' + op, zz, ret)
    return ret


def pkg_installed(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _call_state('pkg.installed', zz, ret)
    return ret


def timesync_service(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    #TODO: assert ntp is not installed (screws up this code)
    zz['service_name'] = 'systemd-timesyncd'
    if not 'Network time on: yes' in _sh('timedatectl status', ret):
        _sh('timedatectl set-ntp true', ret)
        if ret['result']:
            _ret_merge(
                zz,
                ret,
                {
                    'changes': {'new': 'timedatectl set-ntp true'},
                    'comment': 'ntp turned on',
                },
            )
    # Although set-ntp should turn on and enable the daemon,
    # it doesn't seem to on Fedora. This is safe to do.
    return _service_restart(zz, ret)

def _any(items, obj):
    return any(k in obj for k in items)


def _assert_args(zz, args):
    for a in args:
        if not (a in zz and zz[a]):
            raise ValueError('{}: parameter required'.format(a))


def _assert_name(zz_or_name):
    if isinstance(zz_or_name, str):
        name = zz_or_name
    else:
        if 'name' not in zz_or_name:
            zz_or_name['name'] = __lowstate__['name']
        name = zz_or_name['name']
    if not re.search(_SHELL_SAFE_ARG, name):
        raise ValueError('{}: invalid name in kwargs'.format(name))
    return name


def _call_state(state, kwargs, ret):
    zz = copy.deepcopy(kwargs)
    if 'name' not in zz:
        zz['name'] = state
    if not ret['result']:
        return None
    if not '.' in state:
        # not __name__
        state = 'radia' + '.' + state
    new = __states__[state](**zz)
    _debug('state={} ret={}', state, new)
    _inv(zz, new)
    return _ret_merge(zz, ret, new)


def _caller():
    return inspect.currentframe().f_back.f_back.f_code.co_name


@contextlib.contextmanager
def _chdir(d):
    prev_d = os.getcwd()
    try:
        os.chdir(d)
        yield d
    finally:
        os.chdir(prev_d)


def _cluster_config_host(zz, ret, host):

    def guest_f(f):
        return os.path.join(zz['guest_conf_d'], host, f)

    def host_f(f):
        return os.path.join(zz['host_conf_d'], host, f)

    _cluster_ip_and_subnet(zz, host)
    d = os.path.join(zz['host_conf_d'], host)
    _call_state(
        'plain_directory',
        {
            'name': zz['name'] + '.' + host,
            'dir_name': d,
        },
        ret,
    )
    with _chdir(d):
        r = _sh('ssh-keygen -t ecdsa -N "" -f ssh_host_ecdsa_key', ret)
        zz['host_key'] = guest_f('ssh_host_ecdsa_key')
        key = _extract_pub_key('ssh_host_ecdsa_key.pub')
        with open('../known_hosts', 'a') as f:
            f.write('[{}]:{},[{}]:{} {}\n'.format(
                host, zz['ssh_port'], zz['ip'][host], zz['ssh_port'], key))
        zz.setdefault('_guest_cmd', {})[host] = guest_f('_sshd')
        zz.setdefault('_host_log', {})[host] = _cluster_docker_log(zz, ret, host_f)
        _cluster_config_plain_file(
            zz, ret, host_f, ('sshd_config', '_sshd.sh'))


def _cluster_config_master(zz, ret):

    def guest_f(f):
        return os.path.join(zz['guest_conf_d'], f)

    def host_f(f):
        return os.path.join(zz['host_conf_d'], f)

    zz['ip'] = {}
    zz['mpi_subnet'] = _cluster_ip_and_subnet(zz, zz['mpi_master_host'])
    _sh('ssh-keygen -t rsa -N "" -f id_rsa', ret)
    zz['identity_file'] = guest_f('id_rsa')
    zz['user_known_hosts_file'] = guest_f('known_hosts')
    zz['authorized_keys_file'] = guest_f('id_rsa.pub')
    zz['ssh_cmd'] = '/usr/bin/ssh -F {}'.format(guest_f('ssh_config'))
    zz['guest_hosts_f'] = guest_f('hosts')
    zz['guest_user_sh'] = os.path.join(zz['guest_root_d'], zz['user_sh_basename'])
    _cluster_config_plain_file(zz, ret, host_f, ('_run.sh', 'ssh.sh', 'ssh_config') )
    zz['_master_log'] = _cluster_docker_log(
        zz, ret, lambda x: os.path.join(zz['host_root_d'], x))
    zz['_master_cmd'] = guest_f('_run')
    h = ''
    for host, slots in zz['hosts'].items():
        h += '{0} slots={1} max-slots={1}\n'.format(host, slots)
    with open('hosts', 'w') as f:
        f.write(h)


def _cluster_config_plain_file(zz, ret, host_f, basenames):
    for b in basenames:
        _call_state(
            'plain_file',
            {
                'name': zz['name'] + '.' + b,
                'file_name': host_f(b).replace('.sh', ''),
                'source': os.path.join(zz['source_uri'], b),
                'mode': 500 if b.endswith('.sh') else 400,
                'zz': zz,
            },
            ret,
        )


def _cluster_docker_log(zz, ret, host_f):
    f = host_f('radia-mpi.log')
    # Prevents confusing output, because plain_file would
    # output a difference from the previous run. It's not
    # like we are tracking all creates here.
    _sh('dd if=/dev/null of={}'.format(f), ret)
    return f


def _cluster_ip_and_subnet(zz, host):
    """POSIT: class C only"""
    # gethostbyname returns 127.0.0.1 *always* on host it is executed
    addr = subprocess.check_output(['dig', host, '+short']).rstrip('\n')
    zz['ip'][host] = addr
    res = _IPV4_ADDR.sub(r'\g<1>0/24', addr)
    assert res != addr, \
        '{} != {}: {} subnet replace failed: '.format(addr, res, host)
    if 'mpi_subnet' in zz:
        assert res == zz['mpi_subnet'], \
            '{}: {} not on same subnet as master {} ({})'.format(
                res, host, zz['mpi_master_host'], zz['mpi_subnet'])
    return res


def _cluster_start_args(zz, ret):
    _pillar(zz, 'docker_tls_client')
    _assert_args(zz, ['guest_user', 'host_user', 'hosts', 'host_root_d_fmt', 'guest_root_d_fmt', 'ssh_port', 'source_uri'])
    for x in 'guest', 'host':
        r = x + '_root_d'
        # Needed because jupyterhub puts {username} in the notebook
        f = zz[r + '_fmt'].format(username=__pillar__['username'])
        zz[r] = f
        zz[x + '_conf_d'] = os.path.join(f, zz['conf_basename'])
    zz['guest_output_prefix'] = os.path.join(zz['guest_root_d'], zz['output_base'])
    zz['debug_var'] = '1' if zz['debug'] else ''
    tls_args = zz.copy()
    tls_args['name'] += '.' + 'docker_tls_client'
    _call_state('docker_tls_client', tls_args, ret)
    return ret


def _cluster_start_args_assert(zz, ret):
    if not os.path.exists(zz['host_root_d']):
        return _err(
            zz, ret,
            '{host_root_d}: host_root_d does not exist')
    zz['host_user_sh'] = os.path.join(zz['host_root_d'], zz['user_sh_basename'])
    if not os.path.exists(zz['host_user_sh']):
        return _err(
            zz, ret, '{host_user_sh}: start script does not exist')
    pat = os.path.join(zz['host_root_d'].format(username='*'), zz['conf_basename'])
    found = glob.glob(pat)
    if found:
        return _err(zz, ret, '{}: directories exist, remove first', found)
    return


def _cluster_start_containers(zz, ret):

    def start(host):
        env = _docker_tls_env(zz, host)
        _call_state(
            'docker_image',
            {
                'name': zz['name'] + '.image.' + host,
                'image_name': zz['image_name'],
                'want_update': True,
                'docker_env': env,
            },
            ret,
        )
        # We already know the directories don't exist so containers
        # can't run anyway.
        _sh(
            'docker rm --force {_container}'.format(**zz),
            ret,
            ignore_errors=True,
            env=env,
        )
        time.sleep(zz['nfs_sync_sleep_after_conf'])
        _sh(
            'docker run --tty --detach --log-driver=journald --net=host'
            " --user {guest_user} -e RADIA_RUN_CMD='{_cmd}' -e RADIA_DEBUG={debug_var}"
            ' -v {host_root_d}:{guest_root_d}'
            ' --name {_container} {image_name}'.format(**zz),
            ret,
            env=env,
        )
        _sh('nohup docker logs --follow {_container} >> {_log} 2>&1 &'.format(**zz),
            ret,
            env=env,
        )

    zz['image_name'] = _docker_image_name(zz['image_name'])
    zz['_container'] = zz['host_container_name']
    for h in zz['hosts']:
        zz['_cmd'] = zz['_guest_cmd'][h]
        zz['_log'] = zz['_host_log'][h]
        start(h)
    zz['_cmd'] = zz['_master_cmd']
    zz['_log'] = zz['_master_log']
    zz['_container'] = zz['master_container_name']
    start(zz['mpi_master_host'])
    return ret


def _debug(fmt, *args, **kwargs):

    def stringify(v):
        if isinstance(v, (dict, list, collections.Sized)) and len(v) > 4:
            return yaml.dump(v, default_flow_style=False, indent=2)
        return v

    if not isinstance(fmt, str):
        fmt = '{}'
        args = [fmt]
    args = [stringify(x) for x in args]
    kwargs = dict((k, stringify(v)) for k, v in kwargs.items())
    s = ('{}.{}: ' + fmt).format('radia', _caller(), *args, **kwargs)
    _log.debug('%s', s)


def _docker_container_args(kwargs):
    # Called from multiple places so hardwire caller
    zz, ret = _state_init(kwargs, caller='docker_container')
    if not ret['result']:
        return zz, ret
    #TODO: args need to be sanitized (safe_name with spaces for env)
    zz['service_name'] = zz['container_name']
    start = '{program} run --tty --log-driver=journald --name {container_name}'.format(**zz)
    guest_user = zz.get('guest_user')
    _assert_name(guest_user)
    if guest_user:
        start += ' -u ' + guest_user
    start += _docker_container_args_pairs(zz)
    if zz.get('want_docker_sock', False):
        f = zz['sock']
        start += ' -v {}:{}'.format(f, f)
    if zz.get('want_net_host', False):
        start += ' --net=host'
    start += ' ' + _docker_image_name(zz['image_name'])
    #TODO: allow array or use sh -c
    cmd = zz.get('cmd', None)
    if cmd:
        start += ' ' + cmd
    zz['start'] = start
    zz['remove'] = '{program} rm --force {container_name}'.format(**zz)
    zz['stop'] = '{program} stop --time={stop_time} {container_name}'.format(**zz)
    after = [s + '.service' for s in zz.get('after', [])]
    zz['after'] = ' '.join(after + ['docker.service'])
    return zz, ret


def _docker_container_args_pairs(zz):
    is_env = False

    def _clean(e):
        if is_env:
            assert len(e) == 2, \
                '{}: env values must be two elements'.format(e)
        elif not isinstance(e, (list, tuple)):
            e = (e, e)
        elif len(e) < 2:
            # will fail for len=0
            e = (e[0], e[0])
        e = map(str, e)
        map(_assert_name, e)
        return e

    args = ''
    for key, flag in _DOCKER_FLAG_PAIRS.iteritems():
        if key not in zz or not zz[key]:
            # canonicalize for 'init'
            zz[key] = []
            continue
        is_env = key == 'env'
        sep = '=' if is_env else ':'
        # canonicalize for 'init'
        zz[key] = map(_clean, zz[key])
        for v in zz[key]:
            s = ' ' + flag + ' ' + sep.join(v)
            # The :Z sets the selinux context to the appropriate
            # Multi-Category Security (MCS)

            # http://www.projectatomic.io/blog/2015/06/using-volumes-with-docker-can-cause-problems-with-selinux/
            if key == 'volumes':
                if not _is_nfs_d(v[0]):
                    s += ':Z'
            args += s
    return args


def _docker_container_init(zz, ret):
    if not (ret['result'] and 'init' in zz):
        return ret
    _assert_args(zz['init'], ['sentinel', 'cmd'])
    zz = _docker_container_init_args(zz)
    s = zz['sentinel']
    if not os.path.isabs(s):
        raise ValueError('{}: sentinel is not absolute path'.format(s))
    if os.path.exists(s):
        return _ret_merge(s, ret, {'comment': 'already initialized (sentinel exists)'})
    _sh('systemctl stop ' + zz['service_name'], {'result': True}, ignore_errors=True)
    _sh(zz['remove'], ret, ignore_errors=True)
    _sh(zz['start'], ret)
    if not ret['result']:
        return _ret_merge(s, ret, {'comment': 'init failed'})
    if not os.path.exists(s):
        return _ret_merge(s, ret, {'result': False, 'comment': 'sentinel was not created'})
    return _ret_merge(s, ret, {'comment': 'init succeeded (sentinel created)', 'changes': {'new': 'sentinel created'}})


def _docker_container_init_args(zz):
    # Copy, because there are shallow copies below
    orig_zz = copy.deepcopy(zz)
    zz = orig_zz['init']
    del orig_zz['init']
    _docker_container_init_args_defaults(zz, orig_zz)
    # Parse the original values before inserting flag pairs
    # ASSUMES: _state_init() is called, but shouldn't fail
    # because this it has already been called for this low state.
    # See _init_before_first_state() and minion_update()
    zz, _ = _docker_container_args(zz)
    _docker_container_init_args_pairs(zz, orig_zz)
    # Second time is to prepare "start" after we fix up flag pairs
    zz, _ = _docker_container_args(zz)
    return zz


def _docker_container_init_args_defaults(zz, orig_zz):
    """Copy orig_zz values into zz if not already set"""
    zz['name'] = orig_zz['name'] + '.init'
    for key, orig_v in orig_zz.iteritems():
        if not (key in _DOCKER_FLAG_PAIRS or key in zz):
            zz[key] = orig_v


def _docker_container_init_args_pairs(zz, orig_zz):
    """Insert flag pair values (volumes, ports, etc.) from orig_zz to new zz"""
    for key, orig_v in orig_zz.iteritems():
        if not key in _DOCKER_FLAG_PAIRS:
            continue
        already_exists = set([r[0] for r in zz[key]])
        to_insert = []
        for row in orig_v:
            if not row[0] in already_exists:
                to_insert.append(row)
        _debug('key={} to_insert={}', key, to_insert)
        zz[key] = to_insert + zz[key]


def _docker_image_exists(image, ret):
    res = _sh('docker images', ret)
    if not ret['result']:
        return None, ret
    # docker.io/foo/bar or foo/bar is the image so can't use a name to filter
    pat = '(?:^|/)' + image.replace(':', r'\s+') + r'\s+'
    res = res and re.search(pat, res, flags=re.MULTILINE + re.IGNORECASE)
    return res, ret


def _docker_image_name(image):
    _assert_name(image)
    if ':' in image:
        return image
    return image + ':' + _assert_name(__pillar__['pykern']['channel'])


def _docker_service_tls(zz, ret):
    if not (ret['result'] and zz['want_tls']):
        zz['tls_options'] = ''
        return ret
    # Won't override docker_service_tls or kwargs so docker
    _pillar(zz, 'docker_tls_client')
    opts = '--host=tcp://0.0.0.0:{} --host=unix://{} --tlsverify'.format(
        zz['tls_port'], zz['sock'])
    _assert_args(zz, _DOCKER_TLS_FLAGS)
    for k in _DOCKER_TLS_FLAGS:
        f = os.path.join('/etc/docker', k + '.pem')
        _call_state(
            'plain_file',
            {
                'name': 'docker_service_tls.' + f,
                'file_name': f,
                'contents': zz[k],
                'user': zz['user'],
                'group': zz['group'],
            },
            ret,
        )
        opts += ' --{} {}'.format(k, f)
    zz['tls_options'] = opts
    return ret

def _docker_tls_env(zz, host):
    env = os.environ.copy()
    env['DOCKER_TLS_VERIFY'] = '1'
    env['DOCKER_CERT_PATH'] = zz['cert_d']
    env['DOCKER_HOST'] = 'tcp://{}:{}'.format(host, zz['tls_port'])
    return env


def _err(zz, ret, fmt, *args, **kwargs):
    kwargs.update(zz)
    return _ret_merge(
        zz,
        ret,
        {
            'result': False,
            'comment': fmt.format(*args, **kwargs),
        },
    )


def _extract_pub_key(filename):
    with open(filename, 'r') as f:
        key = f.read()
    # Remove the name of the key (last word)
    return ' '.join(key.split()[:2])


def _host_user_uid(zz, ret):
    """Ensure host_user's uid is what we expect.

    Fedora:23 Vagrant image has user vagrant 1001, which is a
    change from previous releases (1000) so we have to change
    the uid/gid to keep it consistent. This operation can't
    be executed with salt-call, because you'll be logged in
    as vagrant.
    """
    try:
        u = pwd.getpwnam(zz['user'])
        if u.pw_uid == zz['uid']:
            return
    except KeyError:
        # User doesn't exist, which is fine (non-Vagrant Fedora install)
        return
    # Need to fix; Something that user.present can't do
    _sh('usermod -u {uid} {user}'.format(**zz), ret)
    _sh('groupmod -g {uid} {user}'.format(**zz), ret)
    _sh('chgrp -R {user} {pw_dir}'.format(pw_dir=u.pw_dir, **zz), ret)


def _init_before_first_state():
    global _initialized
    if _initialized:
        return
    global _inventory, _log, radia
    _initialized = True
    _log = logging.getLogger(__name__)
    _log.debug('_init_before_first_state')
    assert not __opts__['test'], 'test mode not supported'
    now = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    radia = __salt__['radia.module']()
    _inventory = _pillar(caller='mod_init', key='inventory').format(now=now)
    # The _inv() call in _call_state() happens after the
    # call to the state so it's safe to do this. This
    # handles the makedirs properly.
    d = os.path.dirname(_inventory)
    if not os.path.exists(d):
        os.makedirs(d)
    _inv({'start': now})
    return _call_state('minion_update', {}, _ret_init({'name': 'mod_init'}))


def _inv(kwargs, ret=None):
    zz = copy.deepcopy(kwargs)
    zz['fun'] = _caller()
    try:
        zz['low'] = __lowstate__
    except:
        pass
    if ret:
        zz['ret'] = ret
    with salt.utils.flopen(_inventory, 'a') as f:
        # Appending an array to YAML makes all entries a single array
        f.write(
            yaml.dump([zz], default_flow_style=False, indent=2) + '\n',
        )


def _is_nfs_d(d):
    ret = _ret_init({'name': '_is_nfs_d'})
    return 'nfs' in _sh("stat -f -L -c '%T' {}".format(d), ret, ignore_errors=True)


def _nfs_mount_selinux(zz, ret):
    if not ret['result']:
        return ret
    if not 'enabled' in _sh('sestatus', ret, ignore_errors=True):
        return ret
    all_bools = _sh('getsebool -a', ret)
    changes = ''
    for v in 'virt_use_nfs', 'virt_sandbox_use_nfs', 'virt_sandbox_use_all_caps':
        # Some of these variables do not exist, so check for off.
        # Too rigid of a test, but the only way to do this
        if v + ' --> off' in all_bools:
            _sh('setsebool -P {} on'.format(v), ret)
            changes += ' ' + v
    if not changes:
        return ret
    return _ret_merge(
        zz,
        ret,
        {
            'changes': {
                'new': 'setsebool on: ' + changes,
            },
            'comment': 'selinux enabled for NFS',
        },
    )


def _pillar(zz=None, caller=None, key=None):
    full_key = ['radia', caller or _caller()]
    if key:
         full_key += key.split('.')
    res = __pillar__
    _debug('full_key={}', full_key)
    for k in full_key:
        if k not in res:
            raise KeyError('{}: pillar not found'.format('.'.join(full_key)))
        res = res[k]
    _debug('res={}', res)
    if not zz:
        return res
    for k, v in res.iteritems():
        if not k in zz:
            zz[k] = copy.deepcopy(v)
    return zz


def _require():
    if not 'require' in __lowstate__:
        return []
    return __lowstate__['require'] or []


def _ret_init(kwargs):
    return {
        'result': True,
        'changes': {},
        'pchanges': {},
        'name': kwargs.get('name') or kwargs['service_name'],
        'comment': '',
    }


def _ret_merge(name, ret, new):
    if isinstance(name, dict):
        name = name['name']
    _debug('name={} new={}', name, new)
    for changes_type in 'changes', 'pchanges':
        if changes_type in new and new[changes_type]:
            if not isinstance(new[changes_type], dict):
                # plain_file: !!python/tuple [false, Source file salt://cluster/run.sh not found]
                # cannot convert dictionary update sequence element #0 to a sequence
                new[changes_type] = {'new': new[changes_type]}
            if _any(('old', 'new', 'diff'), new[changes_type]):
                ret[changes_type][name] = new[changes_type]
            else:
                ret[changes_type].update(new[changes_type])
    if 'comment' in new and new['comment']:
        prefix = ''
        if not name in new['comment']:
            prefix = name + ': '
        ret['comment'] += prefix + new['comment']
        if not ret['comment'].endswith('\n'):
            ret['comment'] += '\n'
    if 'result' in new and not new['result']:
        ret['result'] = False
    _debug('ret={}', ret)
    return ret


def _save_ret(zz, ret):
    _saved_returns[zz['name']] = ret
    return ret

def _service_disable(zz, ret):
    if not ret['result']:
        return ret
    changes = []
    comment = []
    _, status = _service_status(zz)
    for s, op in (('enabled', 'disable'), ('active', 'stop')):
        _debug('{}={}', s, status[s])
        if not status[s]:
            continue
        _sh('systemctl {} {}'.format(op, zz['service_name']), ret)
        if not ret['result']:
            return ret
        changes.append(op)
        if not status[s]:
            comment.append('service was {}'.format(s))
    changes = {zz['service_name']: {'new': '; '.join(changes)}} if changes else {}
    return _ret_merge(
        zz['service_name'],
        ret,
        {
            'changes': changes,
            'comment': '; '.join(comment),
        },
    )

def _service_restart(zz, ret, force=False):
    if not ret['result']:
        return ret
    changes = []
    comment = []
    updated = bool(ret['changes'])
    ok, status = _service_status(zz)
    _debug('ok={}', ok)
    _debug('updated={}', updated)
    if updated:
        _sh('systemctl daemon-reload', ret)
        if not ret['result']:
            return ret
        changes.append('daemon-reload')
    for s, op in (('enabled', 'reenable'), ('active', 'restart')):
        _debug('{}={}', s, status[s])
        if not updated and status[s] and not (force and s == 'active'):
            continue
        _sh('systemctl {} {}'.format(op, zz['service_name']), ret)
        if not ret['result']:
            return ret
        changes.append(op)
        if not status[s]:
            comment.append('service was not {}'.format(s))
    if updated and not comment:
        comment.append('restarted')
    changes = {zz['service_name']: {'new': '; '.join(changes)}} if changes else {}
    return _ret_merge(
        zz['service_name'],
        ret,
        {
            'changes': changes,
            'comment': '; '.join(comment),
        },
    )


def _service_status(zz, which=('active', 'enabled')):
    ignored = _ret_init(zz)
    status = {}
    for k in which:
        c = 'systemctl is-{} {}'.format(k, zz['service_name'])
        out = _sh(c, ignored, ignore_errors=True)
        status[k] = bool(re.search('^' + k + r'\b', str(out)))
    return status['active'] and status['enabled'], status


def _sh(cmd, ret, ignore_errors=False, env=None):
    if not ret['result']:
        return ''
    name = 'shell.' + cmd
    stdout = ''
    stderr = ''
    err = None
    try:
        _debug('cmd={} ignore_errors={}', cmd, ignore_errors)
        kwargs = dict(
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if env:
            kwargs['env'] = env
        p = subprocess.Popen(cmd, **kwargs)
        stdout, stderr = p.communicate()
        stdout = stdout.decode('ascii', 'ignore')
        stderr = stderr.decode('ascii', 'ignore')
        _debug('stdout={}', stdout)
        _debug('stderr={}', stderr)
        p.wait()
        if p.returncode != 0:
            err = 'exit={}'.format(p.returncode)
    except Exception as e:
        err = str(e)
        if hasattr(e, 'output'):
            stdout += e.output
            _debug('stdout={}', stdout)
    _debug('err={}', err)
    if not ignore_errors and err:
        _ret_merge(
            name,
            ret,
            {
                'result': False,
                'comment': 'ERROR={} stdout={} stderr={}'.format(
                    err, stdout[-1000:], stderr[-1000:]),
            },
        )
        return ''
    _inv({'name': name, 'stdout': stdout, 'stderr': stderr})
    return '' if err and not ignore_errors else stdout


def _state_init(kwargs, caller=None):
    ret = _init_before_first_state()
    if ret and not ret['result']:
        return None, ret
    _debug('name={}', kwargs.get('name', '<no name>'))
    _debug('low={}', __lowstate__)
    zz = copy.deepcopy(kwargs)
    _pillar(zz, caller or _caller())
    _assert_name(zz)
    ret = _ret_init(zz)
    return zz, _ret_init(zz)


@contextlib.contextmanager
def _temp_dir():
    """Save current directory, mkdtemp, yield, then remove and restore.

    Yields:
        str: newly created directory
    """
    d = None
    prev_d = os.getcwd()
    try:
        d = tempfile.mkdtemp(prefix='salt-radia-')
        os.chdir(d)
        yield d
    finally:
        if d:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        os.chdir(prev_d)
