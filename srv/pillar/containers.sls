# Use secret.py to generate values required for salt/containers.sls
jupyterhub:
  host_name: localhost
  host_port: 8000
{% raw %}
  config_contents: |
    c.Authenticator.admin_users = {'{{ pillar.jupyterhub.admin_user }}',}
    c.JupyterHub.confirm_no_ssl = True
    c.JupyterHub.ip = '0.0.0.0'
    import base64
    c.JupyterHub.cookie_secret = base64.b64decode('{{ pillar.jupyterhub.cookie_secret }}')
    c.JupyterHub.proxy_auth_token = '{{ pillar.jupyterhub.proxy_auth_token }}'
    # Allow both local and GitHub users; Useful for bootstrap
    c.JupyterHub.authenticator_class = 'oauthenticator.GitHubOAuthenticator'
    c.GitHubOAuthenticator.oauth_callback_url = '{{ pillar.jupyterhub.host_name }}/hub/oauth_callback'
    c.GitHubOAuthenticator.client_id = '{{ pillar.jupyterhub.github_client_id }}'
    c.GitHubOAuthenticator.client_secret = '{{ pillar.jupyterhub.github_client_secret }}'
    c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'
    c.DockerSpawner.use_internal_ip = True
    from jupyter_client.localinterfaces import public_ips
    c.JupyterHub.hub_ip = public_ips()[0]
    c.DockerSpawner.container_image = '{{ zz.jupyter_image }}'
{% endraw %}
