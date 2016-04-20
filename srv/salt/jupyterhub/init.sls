include:
  - systemd

{%
    set zz = dict(
        host_conf_d='/var/lib/jupyterhub/conf/',
        guest_conf_d='/srv/jupyterhub/conf/',
        config_base='jupyterhub_config.py',
        service_base='jupyterhub.service',
        salt_url='salt://jupyterhub/',
        cookie_base='cookie',
        docker_build_d='/root/docker-build',
    )
%}
{%
    set _dummy = zz.update(
        host_cookie=zz.host_conf_d + zz.cookie_base,
        guest_cookie=zz.guest_conf_d + zz.cookie_base,
        host_config=zz.host_conf_d + zz.config_base,
        guest_config=zz.guest_conf_d + zz.config_base,
        systemd_service='/etc/systemd/system/' + zz.service_base,
    )
%}
{{ zz.systemd_service }}:
  file.managed:
    - require:
      - service: docker
    - source: {{ zz.salt_url }}{{ zz.service_base }}
    - template: jinja
    - user: root
    - group: root
    - mode: 440
    - context:
      zz: {{ zz }}
    - onchanges_in:
      - cmd: systemd-reload

{{ zz.host_conf_d }}:
  file.directory:
    - makedirs: True
    - user: root
    - group: root
    - mode: 750

{{ zz.host_config }}:
  file.managed:
    - source: {{ zz.salt_url }}{{ zz.config_base }}
    - dir_mode: 750
    - template: jinja
    - user: root
    - group: root
    - mode: 400
    - context:
      zz: {{ zz }}

{{ zz.host_cookie }}:
  file.managed:
    - contents_pillar: jupyterhub:cookie_secret
    - dir_mode: 750
    - user: root
    - group: root
    - mode: 400

jupyterhub-image:
  cmd.script:
    - source: salt://jupyterhub/docker-build.sh
    - template: jinja
    # So script output is shown (it always succeeds)
    - stateful: True
    - unless:
      - test -n "$(docker images -q jupyterhub:{{ pykern_pkconfig_channel }}"
    - require:
      - service: docker

jupyterhub:
  service.running:
    - enable: True
    # onchanges is subtle. It doesn't run the state if there are no changes.
    # watch runs if there are changes OR if the watched state returns True
    # (it acts like require in this case). We want the server to be
    # running always when salt runs so it has to be watch.
    - watch:
      - file: {{ zz.host_cookie }}
      - file: {{ zz.host_config }}
      - file: {{ zz.systemd_service }}
      - cmd: jupyterhub-image

#cat > /etc/sysctl.d/40-bivio-shm.conf <<'EOF'
# Controls the maximum size of a message, in bytes
#kernel.msgmnb = 65536

# Controls the default maxmimum size of a message queue
#kernel.msgmax = 65536

# Controls the maximum shared segment size, in bytes
# 1TB should be enough for any machine we own
#kernel.shmmax = 1099511627776

# Controls the maximum number of shared memory segments, in pages
# (4x shmmax / getconf PAGESIZE [4096])
#kernel.shmall = 1073741824
#EOF

# https://github.com/docker/docker/issues/4213#issuecomment-89316474
# allow docker access of nfs volumes
#setsebool -P virt_use_nfs on
#setsebool -P virt_sandbox_use_nfs on
#echo apa14b.bivio.biz > /etc/hostname
#chcon -Rt svirt_sandbox_file_t /home/vagrant
#mkdir -p /var/db/sirepo
#chown vagrant:vagrant /var/db/sirepo
#echo 'apa11b.bivio.biz:/var-on-zfs/db/sirepo /var/db/sirepo nfs nolock' >> /etc/fstab
#mount -a
