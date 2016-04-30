import contextlib
import datetime
import logging
import os
import os.path
import salt.utils
import tempfile
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

def mod_init():
    if _initialized:
        return
    global _initialized, _inventory, _log
    _initialized = True
    _log = logging.getLogger(__name__)
    now = datetime.utcnow()
    _inventory = _pillar('inventory').format(
        now=now.strftime('%Y%m%d%H%M%S'),
    )
    # The _inv() call in _call_state() happens after the
    # call to the state so it's safe to do this. This
    # handles the makedirs properly
    ret = _ret_init({'name': 'mod_init'})
    _call_state('plain_file', {'name': _inventory, 'contents': ''}, ret)
    assert ret['result'], 'FAIL: ' + str(ret)
    _inv({'start': now})


def plain_file(**kwargs):
    if not ('contents', 'source', 'text') in kwargs:
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
    if 'bivio.docker_sock_semodule' in _require():
        volumes += [_pillar('docker_sock'), _pillar('docker_sock')]
    #TODO: support scalar
    for v in kwargs.get('volumes', []):
        # TODO: mkdir
        s = ' -v ' + ':'.join(v)
        if not v[0] == _pillar('docker_sock'):
            s += ':Z'
        args += s
    for p in kwargs.get('ports', []):
        args += ' -p ' + ':'.join(p)
    for l in kwargs.get('links', []):
        args += ' --link ' + ':'.join(l)
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
    if ret['changed']:
        _sh('systemctl daemon-reload', ret)
        _sh('systemctl enable ' + kwargs['name'], ret)
        _sh('systemctl stop ' + name, ret, ignore_errors=True)
        _sh('systemctl start ' + name, ret)
    return ret

def pkg_installed(**kwargs):
    ret = _ret_init(kwargs)
    _call_state('pkg.installed', kwargs, ret)
    return ret


def docker_image(name, image, version):
    pass


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


def _call_state(state, kwargs, ret):
    if not ret['result']:
        return None
    if not '.' in state:
        state = 'bivio.' + state
    kwargs['name'] = state
    new = __states__[state](**kwargs)
    if new['changes']:
        if ('old', 'new') in new['changes']:
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


def _debug(fmt, **kwargs):
    _log.debug(fmt, kwargs)


def _inv(kwargs):
    what['fun'] = _caller()
    what['low'] = __lowstate__
    with salt.utils.flopen(_inventory, 'a') as f:
        f.write(
            yaml.dump([what], default_flow_style=False, indent=2) + '\n',
        )


def _pillar(key):
    res = __pillar__['bivio.' + _caller() + '.' + key]
    if __grains__.uid != 0 and res.startswith('/'):
        return pwd + res


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
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        if ignore_errors:
            return None
        raise _ErrorReturn(name=str(cmd), comment=''.format(e))
        ret['result'] = False
        ret['comment'] += '{}: ERROR {}'.format(cmd, e)
        return None

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
