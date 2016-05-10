#!/usr/bin/env python
"""Generate secrets for test purposes.

You will need to get real values for:

    * github_client_id
    * github_client_secret
    * admin_user

The rest can be generated this way for production::

    admin_user=xyz github_client_secret=x github_client_id=x python secret.py

You can override any values in the environment:
"""
import base64
import binascii
import os
import random
import string
import yaml
import sys

def main():
    cfg = _environ_override({
        'jupyterhub': {
            'admin_user': 'github_user_name',
            'cookie_secret': base64.b64encode(os.urandom(64)),
            'proxy_auth_token': base64.b64encode(os.urandom(32)),
            'github_client_id': binascii.hexlify(os.urandom(10)),
            'github_client_secret': binascii.hexlify(os.urandom(20)),
            'db_pass': _random_password(),
        },
        'postgresql_jupyterhub': {
            'admin_pass': _random_password(),
        },
    })
    return yaml.dump(cfg, default_flow_style=False, indent=2)


def _environ_override(cfg):
    for c in cfg.values():
        for k in c:
            v = os.environ.get(k)
            if v:
                c[k] = v
    return cfg


def _random_password():
    return ''.join(random.choice(string.letters + string.digits) for _ in range(16))


if __name__ == '__main__':
    sys.stdout.write(main())
