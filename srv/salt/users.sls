{% for name, uid  in pillar.users.iteritems() %}
{{ name }}:
  user.present:
    - uid: {{ uid }}
    - gid_from_name: True
    - createhome: False
    - enforce_password: False
/var/nfs/apa11/home/{{ name }}/{{ grains.host }}:
  file.directory:
    - user: {{ name }}
    - group: {{ name }}
    - mode: 750
    - makedirs: False
    - require:
      - mount: /var/nfs/apa11/home
/home/{{ name }}:
  mount.mounted:
    - device: /var/nfs/apa11/home/{{ name }}/{{ grains.host }}
    - fstype: none
    - opts: bind
    - mkmnt: True

{% endfor %}
