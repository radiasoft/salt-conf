robhome_sonos_settings_json:
  radia.plain_file:
    - file_name: "{{ pillar.robhome.sonos.host_settings_json }}"
    - source: salt://robhome/settings.json

robhome_sonos_presets_json:
  radia.plain_file:
    - file_name: "{{ pillar.robhome.sonos.host_presets_json }}"
    - source: salt://robhome/presets.json

# You can't use standard firewall state, because it requires
# all the configuration for the firewall to be here. It's not
# incremental like other configuration.
robhome_sonos_firewall_xml:
  radia.plain_file:
    - file_name: /etc/firewalld/services/sonos.xml
    - source: salt://robhome/sonos.xml
    - user: root
    - group: root
  cmd.run:
    # Could not get the service to restart properly after adding the rule
    # Need to reload first to notify firewalld about sonos.xml
    - name: systemctl firewalld reload && firewall-cmd --zone=public --add-service=sonos --permanent

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
