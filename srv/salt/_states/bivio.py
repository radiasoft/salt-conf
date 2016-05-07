import contextlib
import copy
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
    _call_state('docker_image', {'name': zz['image']}, ret)
    _call_state(
        'plain_file',
        {
            'name': _pillar('systemd.filename').format(**zz),
            'contents': _pillar('systemd.contents'),
            'zz': zz,
        },
        ret,
    )
    return _service_restart(zz, ret)


def docker_image(**kwargs):
    _debug('kwargs={}', kwargs)
    zz, ret = _state_init(kwargs)
    _call_state('docker_service', {'name': 'docker'}, ret)
    if not ret['result']:
        return ret
    _debug('name={}', zz['name'])
    i = zz['name']
    if not ':' in i:
        i += ':' + _assert_name(__pillar__['channel'])
    exists, ret = _docker_image_exists(i, ret)
    if not ret['result']:
        return ret
    new = {}
    if exists:
        new['comment'] = 'image already pulled'
    else:
        _sh('docker pull ' + i, ret)
        if not ret['result']:
            return ret
        new['comment'] = 'image needed to be pulled'
        new['changes'] = {'new': 'pull image'}
    return _ret_merge(i, ret, new)


def docker_service(**kwargs):
    zz, ret = _state_init(kwargs)
    zz['name'] = 'docker'
    # Ignore incoming name as it doesn't matter for the rest
    if _service_status(zz)[0]:
        return _ret_merge(zz, ret, {'comment': 'service is running'})
    _call_state('pkg_installed', {'name': 'docker'}, ret)
    _call_state('pkg_installed', {'name': 'lvm2'}, ret)
    if not ret['result']:
        return ret
    lvs = _sh('lvs', ret);
    # VirtualBox VMs don't have LVMs so we used the default loopback device
    # and don't need to setup storage
    if lvs and 'docker' not in lvs:
        _sh('docker-storage_setup', ret)
    return _service_restart(zz, ret)


def docker_sock_semodule(**kwargs):
    zz, ret = _state_init(kwargs)
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
    return ret


def pkg_installed(**kwargs):
    ret = _ret_init(kwargs)
    if _is_test():
        # Can't acctually install
        return ret
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
    now = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    _inventory = _pillar('inventory').format(now=now)
    # The _inv() call in _call_state() happens after the
    # call to the state so it's safe to do this. This
    # handles the makedirs properly.
    d = os.path.dirname(_inventory)
    if not os.path.exists(d):
        os.makedirs(d)
    with salt.utils.flopen(_inventory, 'w') as f:
        f.write('')
    _inv({'start': now})
    return True


def plain_file(**kwargs):
    zz, ret = _state_init(kwargs)
    if not _any(('contents', 'source', 'text'), zz):
        zz['source'] = _pillar('source').format(**zz)
    if 'zz' in zz:
        zz['context'] = {'zz': zz['zz']}
    for k, v in _pillar('defaults').iteritems():
        zz.setdefault(k, v)
    op = 'managed'
    if zz.get('append', False):
        op = 'append'
        zz['text'] = zz['contents']
    ret = _ret_init(zz)
    _call_state('file.' + op, zz, ret)
    return ret


def _any(items, obj):
    return any(k in obj for k in items)


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
        state = 'bivio' + '.' + state
    new = __states__[state](**zz)
    _debug('state={} ret={}', state, new)
    _inv(zz, new)
    return _ret_merge(zz, ret, new)


def _caller():
    return inspect.currentframe().f_back.f_back.f_code.co_name


def _debug(fmt, *args, **kwargs):
    if not isinstance(fmt, str):
        fmt = '{}'
        args = [fmt]
    s = ('{}.{}: ' + fmt).format('bivio', _caller(), *args, **kwargs)
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
    return zz, ret


def _docker_image_exists(image, ret):
    res = _sh('docker images', ret)
    if not ret['result']:
        return None, ret
    # docker.io/foo/bar or foo/bar is the image so can't use a name to filter
    pat = '(?:^|/)' + image.replace(':', r'\s+') + r'\s+'
    res = res and re.search(pat, res, flags=re.MULTILINE + re.IGNORECASE)
    return res, ret


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


def _is_test():
    #TODO@robnagler better definition of testing
    return __grains__['uid'] != 0


def _pillar(key):
    full_key = ['bivio', _caller()] + key.split('.')
    res = __pillar__
    for k in full_key:
        if k not in res:
            raise KeyError('{}: pillar not found'.format('.'.join(full_key)))
        res = res[k]
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
        prefix = name + ': '
        if new['comment'].startswith(prefix):
            prefix = ''
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
        _sh('systemctl {} {}'.format(op, zz['name']), ret)
        if not ret['result']:
            return ret
        changes.append(op)
        if not status[s]:
            comment.append('service was not {}'.format(s))
    if updated and not comment:
        comment.append('restarted')
    return _ret_merge(
        zz['name'],
        ret,
        {
            'changes': {zz['name']: {'new': '; '.join(changes)}},
            'comment': '; '.join(comment),
        },
    )


def _service_status(zz, which=('active', 'enabled')):
    ignored = _ret_init(zz)
    status = {}
    for k in which:
        c = 'systemctl is-{} {}'.format(k, zz['name'])
        out = _sh(c, ignored, ignore_errors=True)
        status[k] = bool(re.search('^' + k + r'\b', str(out)))
    return status['active'] and status['enabled'], status


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
        return None
    _inv({'name': name, 'stdout': stdout, 'stderr': stderr})
    return None if err else stdout


def _state_init(kwargs):
    _debug('low={}', __lowstate__)
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
