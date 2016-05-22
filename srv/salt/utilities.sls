base_pkgs:
  radia.pkg_installed:
    - pkgs:
      - bind-utils
      - docker
      - emacs-nox
      - lsof
      - openssl
      - screen
      - tar
      - telnet

screenrc_config:
  radia.file_append:
    - file_name: /etc/screenrc
    - text: "escape ^^^^"

ntpd_service:
  radia.ntpd_service: []
