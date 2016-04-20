c.Authenticator.admin_users = {'{{ pillar.jupyterhub.admin_user }}',}
c.JupyterHub.confirm_no_ssl = True
c.JupyterHub.ip = '0.0.0.0'
import base64
c.JupyterHub.cookie_secret = base64.b64decode('{{ pillar.jupyterhub.cookie_secret }}')
c.JupyterHub.proxy_auth_token = '{{ pillar.jupyterhub.proxy_auth_token }}'
# Allow both local and GitHub users; Useful for bootstrap
c.JupyterHub.authenticator_class = 'oauthenticator.GitHubOAuthenticator'
c.GitHubOAuthenticator.oauth_callback_url = 'https://jupyter.radiasoft.org/hub/oauth_callback'
c.GitHubOAuthenticator.client_id = '{{ pillar.jupyterhub.github_client_id }}'
c.GitHubOAuthenticator.client_secret = '{{ pillar.jupyterhub.github_client_secret }}'
