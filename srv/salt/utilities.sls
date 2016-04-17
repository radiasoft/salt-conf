utilities:
  pkg.installed:
    - pkgs:
      - emacs-nox
      - screen
      - telnet

/etc/screenrc:
  file.append:
    - text: "escape ^^^^"
  require:
     - pkg: screen
