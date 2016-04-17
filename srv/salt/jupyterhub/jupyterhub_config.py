c.Authenticator.admin_users = {'{{ pillar.jupyterhub.admin_user }}',}
c.JupyterHub.confirm_no_ssl = True
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.cookie_secret_file = '{{ zz.guest_cookie }}'
c.JupyterHub.proxy_auth_token = '{{ pillar.jupyterhub.proxy_auth_token }}'
