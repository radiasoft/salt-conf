#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""Generate secrets for test purposes.

You will need to get real values for:

    * github_client_id
    * github_client_secret
    * admin_user

The rest can be generated this way for production::

    admin_users=xyz github_client_secret=x github_client_id=x python secret.py

You can override any values in the environment.

Note that admin_users will be split on spaces, because it is a
list.

:copyright: Copyright (c) 2016 RadiaSoft LLC.  All Rights Reserved.
:license: http://www.apache.org/licenses/LICENSE-2.0.html
"""
from __future__ import absolute_import, division, print_function
import base64
import os
import random
import string
import yaml
import sys

def main():
    cfg = _environ_override({
        'jupyterhub': {
            'admin_users': ['vagrant'],
            'authenticator_class': 'jupyterhub.auth.PAMAuthenticator',
            'cookie_secret': base64.b64encode(os.urandom(64)),
            'db_pass': _random_password(),
            'github_client_id': 'replace_me',
            'github_client_secret': 'replace_me',
            'proxy_auth_token': base64.b64encode(os.urandom(32)),
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
                c[k] = v.split(None) if k == 'admin_users' else v
    return cfg


def _random_password():
    return ''.join(random.choice(string.letters + string.digits) for _ in range(16))


if __name__ == '__main__':
    sys.stdout.write(main())
