from dockerspawner import DockerSpawner
from jupyter_client.localinterfaces import public_ips
from tornado import gen
import base64, os
import os.path, pwd
import socket, random, errno

class _Spawner(DockerSpawner):
    def _volumes_to_binds(self, *args, **kwargs):
        binds = super(_Spawner, self)._volumes_to_binds(*args, **kwargs)
        for v in binds:
            if not os.path.exists(v):
                os.mkdir(v)
                if '{{ pillar.jupyter.guest_user}}' != '{{ pillar.jupyterhub.guest_user}}':
                    pw = pwd.getpwnam('{{ pillar.jupyter.guest_user}}')
                    os.chown(v, pw.pw_uid, pw.pw_gid)
        return binds

c.Authenticator.admin_users = set(['{{ pillar.jupyterhub.admin_users|join("', '") }}'])
c.DockerSpawner.container_image = '{{ pillar.jupyter.image_name }}'
c.DockerSpawner.remove_containers = True
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.volumes = {
    '{{ pillar.jupyterhub.host_notebook_d }}': {
        # POSIT: notebook_dir in containers/radiasoft/beamsim-jupyter/build.sh
        'bind': '{{ pillar.jupyterhub.guest_notebook_d }}',
        # NFS is allowed globally the "Z" modifies an selinux context for non-NFS files
    },
    '{{ pillar.jupyterhub.host_scratch_d }}': {
        # POSIT: notebook_dir in containers/radiasoft/beamsim-jupyter/build.sh
        'bind': '{{ pillar.jupyterhub.guest_scratch_d }}',
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
c.JupyterHub.spawner_class = _Spawner

{% if pillar.jupyterhub.debug %}
c.Application.log_level = 'DEBUG'
# Might not want this, but for now it's useful to see everything
#c.JupyterHub.debug_db = True
c.JupyterHub.debug_proxy = True
c.JupyterHub.log_level = 'DEBUG'
c.LocalProcessSpawner.debug = True
c.Spawner.debug = True
{% endif %}

{{ pillar.jupyterhub.aux_contents }}
