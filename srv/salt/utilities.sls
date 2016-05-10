base_pkgs:
  bivio.pkg_installed:
    - pkgs:
      - docker
      - emacs-nox
      - lsof
      - screen
      - tar
      - telnet

screenrc_config:
  bivio.file_append:
    - file_name: /etc/screenrc
    - text: "escape ^^^^"
