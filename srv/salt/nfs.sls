/var/nfs/apa11/home:
  pkgs.installed:
    - pkgs:
      - nfs-utils
  file.directory:
    - user: root
    - group: root
    - mode: 755
    - makedirs: True
  mount.mounted:
    - device: apa11b.bivio.biz:/home
    - fstype: nfs
    - opts: nolock
