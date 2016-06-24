robhome_sonos_settings_json:
  radia.plain_file:
    - file_name: "{{ robhome.sonos.host_settings_json }}"
    - source: salt://robhome/settings.json

robhome_sonos_presets_json:
  radia.plain_file:
    - file_name: "{{ robhome.sonos.host_presets_json }}"
    - source: salt://robhome/presets.json

robhome_sonos_container:
  radia.docker_container:
    - container_name: sonos
    - cmd: "{{ robhome.sonos.guest_conf_d }}/start"
    - image_name: robnagler/sonos
    - want_net_host: True
    - volumes:
      - [ "{{ robhome.sonos.host_settings_json }}",  "{{ robhome.sonos.guest_settings_json }}" ]
      - [ "{{ robhome.sonos.host_presets_json }}",  "{{ robhome.sonos.guest_presets_json }}" ]
