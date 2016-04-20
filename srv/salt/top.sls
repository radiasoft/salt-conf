base:
  '*':
    - update-dnf
    - minion
    - utilities
    - nfs
  apa20b.bivio.biz:
    - docker
    - jupyterhub
    - systemd
  apa19b.bivio.biz:
    - comsol
    - users
