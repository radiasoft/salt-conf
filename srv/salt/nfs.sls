/var/nfs/apa11/home:
  pkg.installed:
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
    # Work around: https://github.com/saltstack/salt/issues/18630
    # opts: rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,na mlen=255,hard,proto=tcp,port=0,timeo=600,retrans=2,sec=sys,clientaddr=192.168.1. 20,local_lock=none,addr=192.168.1.11
    # does not work. vers=4.0 doesn't work.
    # Only run if the directory is not mounted
    - unless:
      - test -d /var/nfs/apa11/home/vagrant
    - opts: nolock
