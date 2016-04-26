/var/lib/bcm:
  file.recurse:
    - source: salt://bcm
    - dir_mode: 700
    - file_mode: 500
    - clean: True
  cmd.run:
    - name: /var/lib/bcm/run.sh
    - stateful: True
