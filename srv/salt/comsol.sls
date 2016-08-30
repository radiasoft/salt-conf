comsol-pkgs:
  pkg.installed:
    - pkgs:
      - libXtst
      - redhat-lsb-core
      - webkitgtk
      - xorg-x11-xauth
      - xterm

comsol_firewall_xml:
  service.running:
    - name: firewalld.service
    - enable: True
  radia.plain_file:
    - file_name: /etc/firewalld/services/comsol.xml
    - source: salt://comsol/comsol.xml
    - user: root
    - group: root
  cmd.run:
    # Could not get the service to restart properly after adding the rule
    # Need to reload first to notify firewalld about sonos.xml
    # TODO(robnagler) the firewalld doesn't seem to modify iptables until a restart
    - name: systemctl reload firewalld && firewall-cmd --zone=public --add-service=comsol --permanent && systemctl restart firewalld

comsol_user:
  group.present:
    - name: comsol
    - gid: 525
  user.present:
    - name: comsol
    - fullname: COMSOL
    - home: /var/comsol
    - uid: 525
    - gid: comsol

comsol_systemd:
  service.running:
    - name: lmcomsol.service
    - enable: True
  radia.plain_file:
    - file_name: /etc/systemd/system/comsol.service
    - source: salt://comsol/comsol.service
    - user: root
    - group: root
  # user/group: comsol:525
  service.running:
    - name: comsol.service
    - enable: True
    # need a watch
