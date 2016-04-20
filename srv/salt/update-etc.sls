createhome-no:
  file.replace:
    - path: /etc/login.defs
    - pattern: "^#\\s*CREATE_HOME.*"
    - repl: CREATE_HOME no
