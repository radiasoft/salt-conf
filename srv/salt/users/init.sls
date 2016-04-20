include:
  - update-etc

{% for name, uid  in pillar.users.iteritems() %}
{{ name }}:
  group.present:
    - gid: {{ uid }}
  user.present:
    - uid: {{ uid }}
    - gid: {{ uid }}
    # https://github.com/saltstack/salt/issues/28726
    # This doesn't work without update-etc./etc/etc/login.defs
    - require:
      - file: /etc/login.defs
    - createhome: False
    - enforce_password: False
/home/{{ name }}:
  mount.mounted:
    - device: /var/nfs/apa11/home/{{ name }}
    - fstype: none
    - opts: bind
    - mkmnt: True
{% endfor %}
