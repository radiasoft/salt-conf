import contextlib
import datetime
import inspect
import logging
import os
import os.path
import salt.utils
import subprocess
import tempfile
import time
import yaml

_initialized = False

'''
def docker_update():
    update and restart
    restart all containers
    need to know what order though
    containers

def pkg_update():
    need to udpate all known packages and reboot

'''

def mod_init(low):
    global _initialized
    if _initialized:
        return True
    assert not __opts__['test'], 'test mode not supported'
    global _inventory, _log
    _initialized = True
    _log = logging.getLogger(__name__)
    now = datetime.datetime.utcnow()
    _inventory = _pillar('inventory').format(
        now=now.strftime('%Y%m%d%H%M%S'),
    )
    # The _inv() call in _call_state() happens after the
    # call to the state so it's safe to do this. This
    # handles the makedirs properly
    ret = _ret_init({'name': 'mod_init'})
    _inventory = _pillar('inventory').format(now=_inventory)
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
    ret = _ret_init(kwargs)
    #docker_image(image)
    args = '--name ' + kwargs['name']
    user = kwargs.get('user', _pillar('user'))
    if user:
        args += ' -u ' + user
    #TODO: support scalar
    for v in kwargs.get('volumes', []):
        # TODO: mkdir???
        # TODO: quote arg
        s = ' -v ' + ':'.join(v) + ':Z'
        if not v[0] == _pillar('docker_sock'):
            s += ':Z'
        args += s
    if kwargs.get('docker_sock', False):
        args += ' -v ' + _pillar('docker_sock')
    for p in kwargs.get('ports', []):
        args += ' -p ' + ':'.join(p)
    for l in kwargs.get('links', []):
        args += ' --link ' + ':'.join(l)
    for e in kwargs.get('env', []):
        args += " -e '" + '='.join(e) + "'"
    args += ' ' + kwargs['image']
    cmd = kwargs.get('cmd')
    if cmd:
        args += ' ' + cmd
    kwargs['args'] = args
    after = [s + '.service' for s in kwargs.get('after', [])]
    kwargs['after'] = ' '.join(after + ['docker.service'])
    fn = _pillar('systemd.filename').format(kwargs)
    if not _call_state(
        'plain_file',
        {
            'name': fn,
            'contents': _pillar('systemd.contents'),
            'zz': kwargs,
        },
        ret,
    ):
        return ret
    if ret['changes']:
        _sh('systemctl daemon-reload', ret)
        _sh('systemctl enable ' + kwargs['name'], ret)
        _sh('systemctl stop ' + name, ret, ignore_errors=True)
        _sh('systemctl start ' + name, ret)
    return ret


def pkg_installed(**kwargs):
    ret = _ret_init(kwargs)
    _call_state('pkg.installed', kwargs, ret)
    return ret


def docker_image(**kwargs):
    ret = _ret_init(kwargs)
    i = kwargs['image'] + ':' + __pillar__['channel']
    res = _sh("docker images -q '{}'".format(i), ret)
    if res is None:
        return ret
    if len(res) == 0:
        _sh("docker pull '{}'".format(i), ret)
    else:
        ret['comment'] += 'image {} already pulled'.format(i)
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


def _any(items, obj):
    return any(k in obj for k in items)


def _call_state(state, kwargs, ret):
    if not ret['result']:
        return None
    if not '.' in state:
        state = __name__ + '.' + state
    new = __states__[state](**kwargs)
    if new['changes']:
        if _any(('old', 'new'), new['changes']):
            ret[kwargs['name']] = new['changes']
        else:
            ret.update(new['changes'])
    if new['comment']:
        ret['comment'] += new['comment']
        if not ret['comment'].endswith('\n'):
            ret['comment'] += '\n'
    if not new['result']:
        ret['result'] = False
        return False
    _inv(kwargs)
    return True


def _caller():
    return inspect.currentframe().f_back.f_back.f_code.co_name


def _debug(fmt, *args, **kwargs):
    if not isinstance(fmt, str):
        fmt = '{}'
        args = [fmt]
    s = ('{}.{}: ' + fmt).format(__name__, _caller(), *args, **kwargs)
    _log.debug('%s', s)


def _inv(kwargs):
    kwargs['fun'] = _caller()
    kwargs['low'] = __lowstate__
    with salt.utils.flopen(_inventory, 'a') as f:
        f.write(
            yaml.dump([kwargs], default_flow_style=False, indent=2) + '\n',
        )


def _pillar(key):
    res = __pillar__['bivio'][_caller()][key]
    if isinstance(res, str) and __grains__['uid'] != 0 and os.path.isabs(res):
        # os.path.join doesn't work b/c res isabs
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


def _sh(cmd, ret, ignore_errors=False):
    if not ret['result']:
        return None
    out = None
    err = None
    e2 = None
    try:
        _debug(cmd)
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        p.wait()
    except Exception as e:
        e2 = e
        if err is None:
            err = str(e2)
        else:
            err += '\n' + e2
    if e2 or p.returncode != 0:
        if ignore_errors:
            return None
        ret['result'] = False
        ret['comment'] += '{}: ERROR={} stdout={} stderr={}'.format(
            cmd, e2 or p.returncode, out, err)
        return None
    return out

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
