/etc/login.defs:
  file.line:
    - match: "^#\\s*CREATE_HOME"
    - contents: CREATE_HOME no
    - mode: replace
