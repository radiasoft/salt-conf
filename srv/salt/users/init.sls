{% for name, uid  in pillar.users.iteritems() %}
{{ name }}:
  group.present:
    - gid: {{ uid }}
  user.present:
    - uid: {{ uid }}
    - gid: {{ uid }}
    - createhome: False
    - enforce_password: False
/home/{{ name }}:
  mount.mounted:
    - device: /var/nfs/apa11/home/{{ name }}
    - fstype: none
    - opts: bind
    - mkmnt: True
{% endfor %}
