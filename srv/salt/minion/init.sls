/etc/salt/call-apply.sh:
  file.managed:
    - content: "salt-call saltutil.sync_all && salt-call saltutil.refresh_pillar && salt-call -l debug state.apply 2>&1 | tee err"
    - user: root
    - group: root
    - mode: 550

/etc/salt/minion.d/bivio.conf:
  file.managed:
    - source: salt://minion/bivio.conf
    - user: root
    - group: root
    - mode: 440
