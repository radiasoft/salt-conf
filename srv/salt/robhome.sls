robhome_sonos_settings_json:
  radia.plain_file:
    - file_name: "{{ pillar.robhome.sonos.host_settings_json }}"
    - source: salt://robhome/settings.json

robhome_sonos_presets_json:
  radia.plain_file:
    - file_name: "{{ pillar.robhome.sonos.host_presets_json }}"
    - source: salt://robhome/presets.json

robhome_sonos_firewall:
  radia.plain_file:
    - file_name: /etc/firewalld/services/sonos.xml
    - source: salt://robhome/sonos.xml
    - user: root
    - group: root
  cmd.run:
    - name: firewall-cmd --add-service=sonos --permanent
  service.running:
    - name: firewalld.service
    - enable: True
    - watch:
      - file: /etc/firewalld/services/sonos.xml

robhome_sonos_container:
  radia.docker_container:
    - container_name: sonos
    - cmd: "{{ pillar.robhome.sonos.guest_conf_d }}/start"
    - image_name: robnagler/sonos
    - want_net_host: True
    - makedirs: False
    - volumes:
      - [ "{{ pillar.robhome.sonos.host_settings_json }}",  "{{ pillar.robhome.sonos.guest_settings_json }}" ]
      - [ "{{ pillar.robhome.sonos.host_presets_json }}",  "{{ pillar.robhome.sonos.guest_presets_json }}" ]
