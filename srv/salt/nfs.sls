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
    - fstype: nfs4
    # Work around: https://github.com/saltstack/salt/issues/18630
    - opts: rw,relatime,vers=4.0,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,port=0,timeo=600,retrans=2,sec=sys,clientaddr={{ grains.fqdn_ip4[0] }},local_lock=none,addr=192.168.1.11
