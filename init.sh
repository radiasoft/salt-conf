#!/bin/bash
#
# Run once
#
f=srv/pillar/apa20b.sls
if [[ ! -f $f ]]; then
    # tornado.web._create_signature_v2 uses sha256 so need 256 bits max (32 bytes):
    # https://tools.ietf.org/html/rfc4868#section-2.1.1
    cookie_secret=$(openssl rand -base64 32)
    # This is passed around verbatim so just a long key that can fit
    # In the "Authorization: token $proxy_auth_token" header.
    proxy_auth_token=$(openssl rand -base64 128)
    echo -n 'admin_user: '
    read admin_user
    cat <<EOF > "$f"
jupyterhub:
  admin_user: $admin_user
  cookie_secret: $cookie_secret
  proxy_auth_token: $proxy_auth_token
EOF
fi
