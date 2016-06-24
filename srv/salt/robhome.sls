robhome_sonos_settings_json:
  radia.plain_file:
    - file_name: "{{ pillar.robhome.sonos.host_settings_json }}"
    - source: salt://robhome/settings.json

robhome_sonos_presets_json:
  radia.plain_file:
    - file_name: "{{ pillar.robhome.sonos.host_presets_json }}"
    - source: salt://robhome/presets.json

robhom_sonos_firewall:
  firewalld.present:
    - name: public
    - ports:
        - {{ pillar.robhome.sonos.port }}/tcp
        - {{ pillar.robhome.sonos.callback_port }}/tcp
        # Need this so they aren't deleted
        - dhcpv6-client
        - mdns
        - ssh


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
