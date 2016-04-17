docker:
  pkg.installed: []
  cmd.script:
    - source: salt://docker/storage-setup.sh
    - unless:
      - lvs | grep -s -q docker
  service.running:
    - enable: True
