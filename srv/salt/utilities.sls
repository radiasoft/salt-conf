utilities:
  pkg.installed:
    - pkgs:
      - emacs-nox
      - screen
      - telnet
      - tar
      - lsof

/etc/screenrc:
  file.append:
    - text: "escape ^^^^"
  require:
     - pkg: screen
