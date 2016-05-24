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

import contextlib
import copy
import datetime
import inspect
import logging
import os
import os.path
import pwd
import re
import salt.utils
import subprocess
import tempfile
import time
import yaml

_initialized = False

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
    _call_state(
        'plain_directory',
        {
            'name': zz['container_name'] + '.host_d',
            'dir_name': zz['host_d'],
        },
        ret,
    )
    with _chdir(zz['host_d']):
        zz['host_root_d'] = os.getcwd()
        _cluster_config_master(zz, zz['guest_d'], ret)
        for host in zz['hosts']:
            _cluster_config_host(zz, zz['guest_d'], host, ret)
    _sh('chown -R {user}:{group} {host_d}'.format(**zz), ret)
    _sh('chmod -R go= {host_d}'.format(**zz), ret)
    return _cluster_start_containers(zz, ret)


def docker_container(**kwargs):
    """Initiate a docker container as a systemd service."""
    # Needs to be set here for _caller() to be right
    zz, ret = _docker_container_args(kwargs)
    if not ret['result']:
        return ret
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
    return _service_restart(zz, ret)


def docker_image(**kwargs):
    zz, ret = _state_init(kwargs)
    if not ret['result']:
        return ret
    _call_state('docker_service', {}, ret)
    if not ret['result']:
        return ret
    i = zz['image_name']
    _assert_name(i)
    if not ':' in i:
        i += ':' + _assert_name(__pillar__['pykern']['channel'])
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


def _cluster_config_host(zz, guest_d, host, ret):

    def guest_f(f):
        return os.path.join(guest_d, host, f)

    tag='XYZZY'
    res = _sh('docker --tlsverify --host="{}" inspect -f {} {}'.format(host, tag, zz['container_name']), ret, ignore_errors=True)
    if tag in res:
        return _ret_merge(zz, ret, {'result': False, 'comment': '{}: container {} exists, need to radia.cluster_stop'.format(host, zz['container_name'])})
    d = os.path.join(zz['host_root_d'], host)
    _call_state(
        'plain_directory',
        {
            'name': zz['name'] + '.' + host,
            'dir_name': d,
        },
        ret,
    )
    with _chdir(d):
        _sh('ssh-keygen -t ecdsa -N "" -f ssh_host_ecdsa_key', ret)
        zz['host_key'] = guest_f('ssh_host_ecdsa_key')
        with open('ssh_host_ecdsa_key.pub') as f:
            key = f.read()
        with open('../known_hosts', 'a') as f:
            f.write('{}:{} {}'.format(host, zz['ssh_port'], key))
        _call_state(
            'plain_file',
            {
                'name': zz['name'] + '.sshd_config',
                'file_name': os.path.join(d, 'sshd_config'),
                'source': os.path.join(zz['source_uri'], 'sshd_config'),
                'zz': zz,
            },
            ret,
        )


def _cluster_config_master(zz, guest_d, ret):

    def guest_f(f):
        return os.path.join(guest_d, f)

    _sh('ssh-keygen -t rsa -N "" -f id_rsa', ret)
    zz['identity_file'] = guest_f('id_rsa')
    zz['user_known_hosts_file'] = guest_f('known_hosts')
    zz['authorized_keys_file'] = guest_f('id_rsa.pub')
    zz['ssh_cmd'] = '/usr/bin/ssh -F {}'.format(guest_f('ssh_config'))
    zz['hosts_f'] = guest_f('hosts')
    zz['cert_d'] = zz['host_root_d']
    for sn in 'run.sh', 'ssh.sh', 'ssh_config':
        fn = sn.replace('.sh', '')
        _call_state(
            'plain_file',
            {
                'name': zz['name'] + '.' + fn,
                'file_name': os.path.join(zz['host_root_d'], fn),
                'source': os.path.join(zz['source_uri'], sn),
                'mode': 400 if fn == sn else 500,
                'zz': zz,
            },
            ret,
        )
    _call_state(
        'docker_tls_client',
        {
            'name': zz['name'] + '.' + 'docker_tls_client',
            'cert_d': zz['cert_d'],
        },
        ret,
    )
    with open('hosts', 'w') as f:
        f.write('\n'.join(zz['hosts']) + '\n')


def _cluster_start_args(zz, ret):
    _assert_args(zz, ['user', 'hosts', 'host_d', 'guest_d', 'ssh_port', 'source_uri'])
    # Needed because jupyterhub puts {username} in the notebook d
    zz['guest_d'] = zz['guest_d'].format(**zz)
    zz['host_d'] = zz['host_d'].format(**zz)
    if os.path.exists(zz['host_d']):
        return _err(zz, ret, '{}: directory exists, remove first', zz['host_d'])
    x = os.path.dirname(zz['host_d'])
    if not os.path.exists(x):
        return _err(zz, ret, '{}: directory does not exist, start container', x)
    return ret


def _cluster_start_containers(zz, ret):
    env = os.environ.copy()
    env['DOCKER_TLS_VERIFY'] = '1'
    env['DOCKER_CERT_PATH'] = zz['cert_d']
    for host in zz['hosts']:
        env['DOCKER_HOST'] = 'tcp://{}:{}'.format(host, zz['docker_tls_port'])
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
    return ret
        # CREATE script that sets RADIARRUN which starts sshd,
        #_sh(cmd + 'pull ' + container_name
        #${cmd[@]} run -v $notebook_d
        #RADIA_RUN="/usr/bin/sshd -D -f $sshd_config"


def _debug(fmt, *args, **kwargs):
    if not isinstance(fmt, str):
        fmt = '{}'
        args = [fmt]
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
    start += ' ' + zz['image_name']
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


def _docker_service_tls(zz, ret):
    if not (ret['result'] and _DOCKER_TLS_FLAGS[0] in zz):
        zz['tls_options'] = ''
        return ret
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
                'user': 'root',
                'group': 'root',
            },
            ret,
        )
        opts += ' --{} {}'.format(k, f)
    zz['tls_options'] = opts
    return ret


def _err(zz, ret, fmt, *args, **kwargs):
    return _ret_merge(
        zz,
        ret,
        {
            'result': False,
            'comment': fmt.format(*args, **kwargs),
        },
    )


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
    global _inventory, _log
    _initialized = True
    _log = logging.getLogger(__name__)
    assert not __opts__['test'], 'test mode not supported'
    now = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
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


def _pillar(key=None, caller=None):
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
    return res


def _require():
    if not 'require' in __lowstate__:
        return []
    return __lowstate__['require'] or []


def _ret_init(kwargs):
    return {
        'result': True,
        'changes': {},
        'pchanges': {},
        'name': kwargs['name'],
        'comment': '',
    }


def _ret_merge(name, ret, new):
    if isinstance(name, dict):
        name = name['name']
    _debug('name={} new={}', name, new)
    for changes_type in 'changes', 'pchanges':
        if changes_type in new and new[changes_type]:
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


def _service_restart(zz, ret):
    if not ret['result']:
        return ret
    changes = []
    comment = []
    updated = bool(ret['changes'])
    ok, status = _service_status(zz)
    if updated:
        _sh('systemctl daemon-reload', ret)
        if not ret['result']:
            return ret
        changes.append('daemon-reload')
    for s, op in (('enabled', 'reenable'), ('active', 'restart')):
        if not updated and status[s]:
            continue
        _sh('systemctl {} {}'.format(op, zz['service_name']), ret)
        if not ret['result']:
            return ret
        changes.append(op)
        if not status[s]:
            comment.append('service was not {}'.format(s))
    if updated and not comment:
        comment.append('restarted')
    changes = {zz['name']: {'new': '; '.join(changes)}} if changes else {}
    return _ret_merge(
        zz['name'],
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
    stdout = None
    stderr = None
    err = None
    try:
        _debug('cmd={}', cmd)
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
    return '' if err else stdout


def _state_init(kwargs, caller=None):
    ret = _init_before_first_state()
    if ret and not ret['result']:
        return None, ret
    _debug('low={}', __lowstate__)
    zz = copy.deepcopy(kwargs)
    for k, v in _pillar(caller=caller or _caller()).iteritems():
        if not k in zz:
            zz[k] = copy.deepcopy(v)
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
