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
    - source: salt://robhome/sonos.xml
    - user: root
    - group: root
  cmd.run:
    # Could not get the service to restart properly after adding the rule
    # Need to reload first to notify firewalld about sonos.xml
    # TODO(robnagler) the firewalld doesn't seem to modify iptables until a restart
    - name: systemctl reload firewalld && firewall-cmd --zone=public --add-service=comsol --permanent && systemctl restart firewalld
