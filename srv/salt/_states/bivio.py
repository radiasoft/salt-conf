import contextlib
import datetime
import inspect
import logging
import os
import os.path
import re
import salt.utils
import subprocess
import tempfile
import time
import yaml

_initialized = False

_SHELL_SAFE_ARG = re.compile(r'^[-_/:\.\+\@=,a-zA-Z0-9]+$')

'''
def docker_update():
    update and restart
    restart all containers
    need to know what order though
    containers

def pkg_update():
    need to udpate all known packages and reboot

'''

def docker_container(**kwargs):
    """Initiate a docker container as a systemd service.

    # globally unique name
jupyterhub:
  bivio.docker_container:
    - name: "radiasoft/jupyterhub:{{ pillar.channel }}"
    - links: [ postgres:postgres ]
    - volumes: [ {{ zz.host_conf.d }}:{{ zz.guest_conf.d }} ]
    - gueset_user: root
    - dockersock: True
    - ports: [ 5692:8000 ]
    - cmd: jupyterhub -f {{ zz.guest_config }}
    - requires: [ postgres jupyter_singleuser jupyter_config ]
    every object needs to be logged somewhere
    write container to a file (dependencies natural)
        so can know what to restart
    there has to be a state file which contains
       the order of the startup states
       all states run and recreate the state
       with the ability to undo.
       a software update would look at that state
       and decide which services needed to be restarted based
       on changes to docker images
       docker images would need to know if we should quiesce
       the entire system
    dockersock = dockersock
    zz = {}
    do we know??
    """
    zz, ret = _docker_container_args(kwargs)
    _call_state('docker_image', {'name', zz['name']}, ret)
    _call_state(
        'plain_file',
        {
            'name': _pillar('systemd.filename').format(zz),
            'contents': _pillar('systemd.contents'),
            'zz': zz,
        },
        ret,
    )
    return _service_running(zz, ret)


def docker_image(**kwargs):
    zz, ret = _state_init(kwargs)
    i = zz['name'] + ':' + _assert_name(name=__pillar__['channel'])
    res = _sh('docker images -q ' i, ret)
    if not ret['result']:
        return ret
    new = {}
    if len(res) == 0:
        _sh("docker pull '{}'".format(i), ret)
        if not ret['result']:
            return ret
        new['comment'] = i + ' was not local'
        new['changes'] = {'new': 'pull image'}
    else:
        new['comment'] = i + ' already local'
    return _ret_merge(i, ret, new)


def docker_service(**kwargs):
    ret = _ret_init(kwargs)
    if _sh('systemctl status docker', ret, ignore_errors=True):
        ret['comment'] = 'docker service is already running'
        return ret
    _call_state('pkg_installed', {'name': 'docker'}, ret)
    _call_state('pkg_installed', {'name': 'lvm2'}, ret)
    lvs = _sh('lvs', ret);
    # VirtualBox VMs don't have LVMs so we used the default loopback device
    # and don't need to setup storage
    if lvs and 'docker' not in lvs:
        _sh('docker-storage_setup', ret)
    _sh('systemctl enable docker', ret)
    _sh('systemctl start docker', ret)
    for _ in xrange(3):
        time.sleep(1)
        if _sh('systemctl status docker', ret, ignore_errors=True):
            ret['changes']['docker.service'] = {
                'old': 'stopped',
                'new': 'started',
            }
            ret['comment'] += '\n'
            return ret
    return ret


def docker_sock_semodule(**kwargs):
    ret = _ret_init(kwargs)
    modules = _sh('semodule -l', ret)
    if modules is None or _pillar('name') in modules:
        return ret
    with _temp_dir() as d:
        _call_state(
            'plain_file',
            {
                'name': os.path.join(d, 'z.te'),
                'contents': _pillar('contents'),
            },
            ret,
        )
        _sh('checkmodule -M -m z.te -o z.mod', ret)
        _sh('semodule_package -m z.mod -o z.pp', ret)
        _sh('semodule -i z.pp', ret)


def pkg_installed(**kwargs):
    ret = _ret_init(kwargs)
    _call_state('pkg.installed', kwargs, ret)
    return ret


def mod_init(low):
    global _initialized
    if _initialized:
        return True
    assert not __opts__['test'], 'test mode not supported'
    global _inventory, _log
    _initialized = True
    ret = _ret_init({'name': 'mod_init'})
    _log = logging.getLogger(__name__)
    now = datetime.datetime.utcnow()
    _inventory = _pillar('inventory').format(
        now=now.strftime('%Y%m%d%H%M%S'),
    )
    # The _inv() call in _call_state() happens after the
    # call to the state so it's safe to do this. This
    # handles the makedirs properly.
    d = os.path.dirname(_inventory)
    if not os.path.exists(d):
        os.makedirs(d)
    with salt.utils.flopen(_inventory, 'w') as f:
        f.write('')
    #_inv({'start': now})
    return True


def plain_file(**kwargs):
    if not _any(('contents', 'source', 'text'), kwargs):
        kwargs['source'] = _pillar('source').format(kwargs)
    if 'zz' in kwargs:
        kwargs['context'] = {'zz': kwargs['zz']}
    for k, v in _pillar('defaults').iteritems():
        kwargs.setdefault(k, v)
    op = 'managed'
    if kwargs.get('append', False):
        op = 'append'
        kwargs['text'] = kwargs['contents']
    ret = _ret_init(kwargs)
    _call_state('file.' + op, kwargs, ret)
    return ret


def _any(items, obj):
    return any(k in obj for k in items)


def _assert_name(zz=None, name=None):
    if not name:
        if 'name' not in zz:
            raise KeyError('{}: state kwargs missing name'.format(zz))
        name = zz['name']
    if not re.search(_SHELL_SAFE_ARG, name):
        raise ValueError('{}: invalid name in kwargs'.format(name))
    return name


def _call_state(state, kwargs, ret):
    if name not in kwargs:
        kwargs['name'] = state
    if not ret['result']:
        return None
    if not '.' in state:
        state = __name__ + '.' + state
    new = __states__[state](**kwargs)
    _inv(kwargs, new)
    return _ret_merge(ret, kwargs['name'], new)


def _caller():
    return inspect.currentframe().f_back.f_back.f_code.co_name


def _debug(fmt, *args, **kwargs):
    if not isinstance(fmt, str):
        fmt = '{}'
        args = [fmt]
    s = ('{}.{}: ' + fmt).format(__name__, _caller(), *args, **kwargs)
    _log.debug('%s', s)


def _docker_container_args(kwargs):
    zz, ret = _state_init(kwargs)
    args = '--name ' + zz['name']
    user = zz.get('user')
    if user:
        args += ' -u ' + user
    #TODO: support scalar
#TODO: share code
    for v in zz.get('volumes', []):
          # TODO: mkdir??? yes, be
        # TODO: quote arg
        s = ' -v ' + ':'.join(v) + ':Z'
        if not v[0] == _pillar('docker_sock'):
            s += ':Z'
        args += s
    if zz.get('docker_sock', False):
        x = _pillar('docker_sock')
        args += ' -v {}:{}'.format(x, x)
    for p in zz.get('ports', []):
        args += ' -p ' + ':'.join(p)
    for l in zz.get('links', []):
        args += ' --link ' + ':'.join(l)
    for e in zz.get('env', []):
        args += " -e '" + '='.join(e) + "'"
    args += ' ' + zz['image']
    cmd = zz.get('cmd', None)
    if cmd:
        args += ' ' + cmd
    zz['args'] = args
    after = [s + '.service' for s in zz.get('after', [])]
    zz['after'] = ' '.join(after + ['docker.service'])
    return zz


def _inv(kwargs, ret=None):
    res = copy.deepcopy(kwargs)
    res['fun'] = _caller()
    res['low'] = __lowstate__
    if ret:
        res['ret'] = ret
    with salt.utils.flopen(_inventory, 'a') as f:
        # Appending an array to YAML makes all entries a single array
        f.write(
            yaml.dump([res], default_flow_style=False, indent=2) + '\n',
        )


def _pillar(key):
    res = __pillar__['bivio'][_caller()][key]
    #TODO@robnagler better definition of testing
    if isinstance(res, str) and __grains__['uid'] != 0 and os.path.isabs(res):
        # os.path.join doesn't work b/c it won't concatenate abs paths
        return os.getcwd() + res
    return res


def _require():
    if not 'require' in __lowstate__:
        return []
    return __lowstate__['require'] or []


def _ret_init(kwargs):
    return {
        'result': True,
        'changes': {},
        'name': kwargs['name'],
        'comment': '',
    }


def _ret_merge(name, ret, new):
    if 'changes' in new and new['changes']:
        if _any(('old', 'new'), new['changes']):
            ret['changes'][name] = new['changes']
        else:
            ret['changes'].update(new['changes'])
        for v in ret['changes'].values():
            for k in 'old', 'new':
                if k not v:
                    v[k] = None
    if 'comment' in new and new['comment']:
        ret['comment'] += 'name: ' + new['comment']
        if not ret['comment'].endswith('\n'):
            ret['comment'] += '\n'
    if 'result' in new and not new['result']:
        ret['result'] = False
    return ret['result']


def _service_running(zz, ret):
    if not ret['result']:
        return ret
    changes = []
    comment = []
    update = ret['result'] and ret['changes']
    status = _service_status(zz)
    if update:
        _sh('systemctl daemon-reload', ret)
        if not ret['result']:
            return ret
        changes.append('daemon-reload')
    for s, op in (('enabled', 'reenable'), ('active', 'restart')):
        if update or not status[s]:
            _sh('systemctl {} {}'.format(op, zz['name']), ret)
            if not ret['result']:
                return ret
            changes.append(op)
            if not status[s]:
                comment.append('{} was not {}'.format(zz['name'], s))
    if update and not comment:
        comment.append('restarted')
    return _ret_merge(
        n,
        ret,
        {
            'changes': {zz['service_name']: {'new': '; '.join(changes)}},
            'comment': '; '.join('comment'),
        },
    )


def _service_status(zz):
    ignored = ret_init(zz)
    res = {}
    for k in 'active', 'enabled':
        c = 'systemctl is-{} {}'.format(k, zz['service_name'])
        out = _sh(c, ignored, ignore_errors=True)
        res[k] = bool(re.search('^' + k + r'\b', out))
    return res


def _sh(cmd, ret, ignore_errors=False):
    if not ret['result']:
        return None
    name = 'shell: ' + cmd
    stdout = None
    stderr = None
    err = None
    try:
        _debug('cmd={}', cmd)
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = p.communicate()
        _debug('stdout={}', stdout)
        _debug('stderr={}', stderr)
        p.wait()
        if p.returncode != 0:
            err = 'exit={}'.format(p.returncode)
    except Exception as e:
        err = str(e)
    if not ignore_errors or err:
        debug('err={}', err)
        _ret_merge(
            name,
            {
                'result': 'False',
                'comment': 'ERROR={} stdout={} stderr={}'.format(
                    err, stdout[-1000:], stderr[-1000:]),
            },
        )
        return None
    _inv({'name': name, 'stdout': stdout, 'stderr', stderr})
    return None if err else stdout


def _state_init(kwargs):
    zz = copy.deepcopy(kwargs)
    _assert_name(zz)
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
        d = tempfile.mkdtemp(prefix='salt-bivio-')
        os.chdir(d)
        yield d
    finally:
        if d:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        os.chdir(prev_d)
