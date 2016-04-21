include:
  - systemd

{%
    set zz = dict(
        host_conf_d='/var/lib/jupyterhub/conf/',
        guest_conf_d='/srv/jupyterhub/conf/',
        config_base='jupyterhub_config.py',
        service_base='jupyterhub.service',
        salt_url='salt://jupyterhub/',
        docker_build_d='/root/docker-build',
        docker_image='jupyterhub:' + pillar.pykern_pkconfig_channel,
    )
%}
{%
    set _dummy = zz.update(
        host_config=zz.host_conf_d + zz.config_base,
        guest_config=zz.guest_conf_d + zz.config_base,
        systemd_service='/etc/systemd/system/' + zz.service_base,
    )
%}
jupyterhub-pkgs:
  pkg.installed:
    - pkgs:
      - policycoreutils
      - policycoreutils-python
      - checkpolicy

jupyterhub-selinux:
  cmd.script:
    - source: salt://jupyterhub/docker-selinux.sh
    - stateful: True
    - require:
      - service: docker
      - pkg: jupyterhub-pkgs
# To test: python -c 'import docker; docker.Client(base_url="unix://var/run/docker.sock", version="auto").containers()'

{{ zz.systemd_service }}:
  file.managed:
    - require:
      - service: docker
      - pkg: jupyterhub-pkgs
      - cmd: jupyterhub-selinux
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

{{ zz.host_conf_d }}/cookie_secret:
  file.absent: []

#TODO: Need to know when to rebuild. For now, we just: docker rmi jupyter:beta
jupyterhub-image:
  cmd.script:
    - source: salt://jupyterhub/docker-build.sh
    - template: jinja
    # So script output is shown (it always succeeds)
    - stateful: True
    - args: "{{ zz.docker_image }}"
    - unless:
      - test -n "$(docker images -q {{ zz.docker_image }})"
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
