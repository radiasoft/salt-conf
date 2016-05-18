base_pkgs:
  radia.pkg_installed:
    - pkgs:
      - docker
      - emacs-nox
      - lsof
      - screen
      - tar
      - telnet

screenrc_config:
  radia.file_append:
    - file_name: /etc/screenrc
    - text: "escape ^^^^"
