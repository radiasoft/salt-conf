/etc/salt/minion.d/bivio.conf:
  file.managed:
    - source: salt://minion/bivio.conf
    - user: root
    - group: root
    - mode: 440
