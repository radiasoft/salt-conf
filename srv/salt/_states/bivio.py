import tempfile
import contextlib
import logging
import os
import salt.utils
import os.path

log = logging.getLogger(__name__)


def plain_file()
    name is same as dest
    pull from salt
    only one template(?)
    pillar.{{ id }}.source or same as name


def t1(**kwargs):
    log.debug(str(kwargs))
    #log.debug(__salt__.keys())
    #log.debug(__pillar__.keys())
    #log.debug(__grains__.keys())
    #log.debug(__pillar__['channel'])
    log.debug(str(globals().keys()))
    for f in '__low__', '__lowstate__', '__opts__', '__env__', '__context__':
        log.debug(f + '=' + str(globals()[f]))
    ret = __states__['file.managed'](
        name='/tmp/t1.service',
        source='salt://t1.service',
        context=dict(hello='bye2'),
        template='jinja',
    )
    if not ret['result']:
        log.debug('xxx' + str(ret))
        return ret
    log.debug('yyy' + str(ret))
    return {
        'name': kwargs['name'],
        'changes': {
            'this': {'old': '1', 'new': '2'},
            '/tmp/t1.service': ret['changes'],
        },
        'result': True,
        'comment': ret['comment'],
    }


_SYSTEMD_UNIT = """
[Unit]
Description={{ zz.name }}
Requires={{ zz.require }}
After={{ zz.require }}

[Service]
Restart=on-failure
RestartSec=10
# The :Z sets the selinux context to the appropriate Multi-Category Security (MCS)
# http://www.projectatomic.io/blog/2015/06/using-volumes-with-docker-can-cause-problems-with-selinux/
ExecStart=/usr/bin/docker run -t --rm{{ zz.args }}
ExecStop=-/usr/bin/docker stop -t 2 {{ zz.name }}

[Install]
WantedBy=multi-user.target
"""

def docker_container(
        name,
        image,
        links=None,
        volumes=None,
        user='vagrant',
        guest_user=None,
        dockersock=False,
        ports=None,
        after=None,
        cmd=None,
    ):
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
    """
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
    dockersock = salt.utils.is_true(dockersock)
    zz = {}
    require = _require_services()
    try:
        #docker_image(image)
        args = '--name ' + name
        guest_user = user
        if guest_user:
            args += ' -u ' + guest_user
        for v in volumes || []:
            if not exist v[0] :
                _mkdir(v[0], docker.user)
            args += ' -v ' + v + ':Z'

        if dockersock:
            _selinux_dockersock()
            args += ' -v /run/docker.sock:/run/docker.sock'
        for p in ports || []:
            args += ' -p ' + p
        for l in links || []:
            args += ' --link ' + l
        args += ' ' + image
        if cmd:
            args += ' ' + cmd
        after += (' ' if after else '') + 'docker.service'
        fn = '/etc/systemd/system/{}.service'.format(name)
        ret = _install_jinja(name=fn, content=_SYSTEMD_UNIT, zz)
        if ret['changed']:
            if __opts__['test']:
                ret['comment'] += '; would have restarted {}'.format(name)
                return
            _sh('systemctl daemon-reload')
            _sh('systemctl enable ' + name)
            _sh('systemctl stop ' + name, True)
            _sh('systemctl start ' + name)
            # UNDO: systemctl stop {name}
            # UNDO: systemctl disable {name}
        # UNDO: rm -f {fn}
    except _ErrorReturn as e:
        return e.ret

def docker_image(name, image, version):
    if
    pass


class _ErrorReturn(Exception):
    def __init__(self, ret=None, **kwargs):
        if not ret:
            ret = dict(kwargs)
            assert name in ret
            if changed not in ret:
                ret['changed'] = {}
            if comment not in ret:
                ret['comment'] = ''
        # Always
        ret.result = False
        self.ret = ret

    def __str__(self):
        return '_ErrorReturn' + repr(self.value)

def _cache_state(what):
    try:
        with salt.utils.flopen(fn_, 'w+') as fp_:
            fp_.write('')
    return os.path.join(__opts__['cachedir'], 'pkg_refresh')



def _install_jinja(**kwargs):
    del kwargs['zz']
    ret = __states__['file.managed'](
        template='jinja',
        context={'zz': kwargs['zz']},
        **kwargs,
    )
    log.debug('_install_jinja: ', str(ret))
    if not ret['result']:
        raise _ErrorReturn(ret)


def _selinux_dockersock():
    if 'bivio_dockersock' in _sh('semodule -l'):
        return
    #UNDO: semodule -r bivio_dockersock
    with _temp_dir():
        with open('bivio_dockersock.te', 'w') as f:
            f.write("""
module bivio_dockersock 1.0;
require {
    type docker_var_run_t;
    type docker_t;
    type svirt_lxc_net_t;
    class sock_file write;
    class unix_stream_socket connectto;
}
allow svirt_lxc_net_t docker_t:unix_stream_socket connectto;
allow svirt_lxc_net_t docker_var_run_t:sock_file write;
"""
        _sh('checkmodule -M -m bivio_dockersock.te -o bivio_dockersock.mod')
        _sh('semodule_package -m bivio_dockersock.mod -o bivio_dockersock.pp')
        _sh('semodule -i bivio_dockersock.pp')


def _sh(cmd, ignore_errors=False):
    try:
        return subprocess.check_ouput(
            cmd,
            shell=True,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        if ignore_errors:
            return
        raise _ErrorReturn(name=str(cmd), comment='ERROR: {}'.format(e))


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

def docker_update():
    update and restart
    restart all containers
    need to know what order though
    containers
