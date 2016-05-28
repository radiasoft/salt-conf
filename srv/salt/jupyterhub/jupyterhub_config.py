from dockerspawner import DockerSpawner
from jupyter_client.localinterfaces import public_ips
from tornado import gen
import base64, os
import os.path, pwd
import socket, random, errno

# May be overwritten below
c.JupyterHub.spawner_class = DockerSpawner

c.Authenticator.admin_users = set(['{{ pillar.jupyterhub.admin_users|join("', '") }}'])
c.DockerSpawner.container_image = '{{ pillar.jupyter.image_name }}'
c.DockerSpawner.use_internal_ip = False
# Remove containers when the user stops them
c.DockerSpawner.remove_containers = True
class _Spawner(DockerSpawner):
    def get_env(self):
        res = super(_Spawner, self).get_env()
        res['RADIA_RUN_PORT'] = str(self.container_port)
        return res

    def get_ip_and_port(self):
        # Need this yield statement to have "yield from" id dockerspawner.py work
        # There may be a bug in dockerspawner.py
        _dummy = yield self.docker('port', self.container_id, self.container_port)
        return self.container_ip, self.container_port

    def start(self, image=None, extra_create_kwargs=None,
        extra_start_kwargs=None, extra_host_config=None):
        if not extra_start_kwargs:
            extra_start_kwargs = {}
        extra_start_kwargs['network_mode'] = 'host'
        self.container_ip = '{{ pillar.jupyter.ip }}'
        self.container_port = self.__compute_port()
        return super(_Spawner, self).start( image, extra_create_kwargs, extra_start_kwargs, extra_host_config)

    def _volumes_to_binds(self, *args, **kwargs):

        binds = super(_Spawner, self)._volumes_to_binds(*args, **kwargs)
        for v in binds:
            if not os.path.exists(v):
                os.mkdir(v)
                if '{{ pillar.jupyter.guest_user}}' != '{{ pillar.jupyterhub.guest_user}}':
                    pw = pwd.getpwnam('{{ pillar.jupyter.guest_user}}')
                    os.chown(v, pw.pw_uid, pw.pw_gid)
        return binds

    def __compute_port(self):
        """Guess a port that will be open on container_ip"""
        port_range = (9000, 9999)
        for i in range(20):
            # Race: find port => start container => listen port
            # We open a non-emphemeral port since the kernel won't
            # dynamically allocate it during the race. If there's
            # a server already on the port, that's ok, because
            # there are others to choose from.
            p = random.randint(*port_range)
            try:
                # Short timeout since this should be a local connection
                s = socket.create_connection((self.container_ip, p), timeout=0.5)
                s.close()
            except socket.error as e:
                # POSIT: Was not blocked by firewall
                if e.errno == errno.ECONNREFUSED:
                    return p
            except Exception:
                # Maybe didn't open the port
                pass
        raise AssertionError('{}: unable to allocate port in range'.format(port_range))

c.JupyterHub.spawner_class = _Spawner
c.DockerSpawner.volumes = {
    '{{ pillar.jupyterhub.host_notebook_d }}': {
        # POSIT: notebook_dir in containers/radiasoft/beamsim-jupyter/build.sh
        'bind': '{{ pillar.jupyterhub.guest_notebook_d }}',
        # NFS is allowed globally the "Z" modifies an selinux context for non-NFS files
    },
}
c.GitHubOAuthenticator.client_id = '{{ pillar.jupyterhub.github_client_id }}'
c.GitHubOAuthenticator.client_secret = '{{ pillar.jupyterhub.github_client_secret }}'
c.GitHubOAuthenticator.oauth_callback_url = 'https://{{ pillar.jupyterhub.host_name }}/hub/oauth_callback'
c.JupyterHub.authenticator_class = '{{ pillar.jupyterhub.authenticator_class }}'
c.JupyterHub.confirm_no_ssl = True
c.JupyterHub.cookie_secret = base64.b64decode('{{ pillar.jupyterhub.cookie_secret }}')
c.JupyterHub.db_url = 'postgresql://jupyterhub:{{ pillar.jupyterhub.db_pass }}@{{ pillar.jupyterhub.postgresql_name }}:5432/jupyterhub'
c.JupyterHub.hub_ip = public_ips()[0]
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.port = {{ pillar.jupyterhub.guest_port }}
c.JupyterHub.proxy_auth_token = '{{ pillar.jupyterhub.proxy_auth_token }}'
{% if pillar.jupyterhub.debug %}
c.Application.log_level = 'DEBUG'
# Might not want this, but for now it's useful to see everything
c.JupyterHub.debug_db = True
c.JupyterHub.debug_proxy = True
c.JupyterHub.log_level = 'DEBUG'
c.LocalProcessSpawner.debug = True
c.Spawner.debug = True
{% endif %}
{{ pillar.jupyterhub.aux_contents }}
