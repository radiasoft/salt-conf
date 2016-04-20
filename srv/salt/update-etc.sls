# https://github.com/saltstack/salt/issues/28726
# Needed by users.user.present.creathome: False
/etc/login.defs:
  file.replace:
    - pattern: "^#\\s*CREATE_HOME.*"
    - repl: CREATE_HOME no
