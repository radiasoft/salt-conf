/etc/login.defs:
  file.replace:
    - pattern: "^#\\s*CREATE_HOME.*"
    - repl: CREATE_HOME no
