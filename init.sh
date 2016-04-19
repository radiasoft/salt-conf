#!/bin/bash
#
# Run once
#
f=srv/pillar/apa20b.sls
rand_base64() {
    openssl rand -base64 "$1" | tr -d \\n
}

if [[ ! -f $f ]]; then
    # tornado.web._create_signature_v2 uses sha256 so need 256 bits max (32 bytes):
    # https://tools.ietf.org/html/rfc4868#section-2.1.1
    cookie_secret=$(rand_base64 32)
    # This is passed around verbatim so just a long key (not decoded) that can fit
    # In the "Authorization: token $proxy_auth_token" header.
    proxy_auth_token=$(rand_base64 64)
    echo -n 'admin_user: '
    read admin_user
    cat <<EOF > "$f"
jupyterhub:
  admin_user: $admin_user
  cookie_secret: $cookie_secret
  proxy_auth_token: $proxy_auth_token
EOF
fi
