import tempfile
import contextlib
import logging
import os
import salt.utils
import os.path

log = logging.getLogger(__name__)


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
        user=None,
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
    - user: root
    - dockersock: True
    - ports: [ 5692:8000 ]
    - cmd: jupyterhub -f {{ zz.guest_config }}
    - requires: [ postgres jupyter_singleuser jupyter_config ]
    """
    dockersock = salt.utils.is_true(dockersock)
    zz = {}
    require = _require_services()
    try:
        #docker_image(image)
        args = '--name ' + name
        if user:
            args += ' -u ' + user
        for v in volumes || []:
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
