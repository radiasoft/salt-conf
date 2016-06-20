#
# TODO(robnagler) configure backups for postgres
#
sonos_settings_json:
  radia.plain_file:
    - file_name: {{ rob_home.sonos.host_settings_json }}
    - source: salt://rob-home/settings.json

sonos_presets_json:
  radia.plain_file:
    - file_name: "{{ rob_home.sonos.host_presets_json }}"
    - source: salt://rob-home/presets.json

sonos_container:
  radia.docker_container:
    - container_name: radiasoft-sonos
    - cmd: "{{ rob_home.sonos.guest_conf_d }}/start"
    - image_name: radiasoft/sonos
    - want_net_host: True
    - volumes:
      - [ "{{ rob_home.sonos.host_settings_json }}",  "{{ rob_home.sonos.guest_settings_json }}" ]
      - [ "{{ rob_home.sonos.host_presets_json }}",  "{{ rob_home.sonos.guest_presets_json }}" ]
