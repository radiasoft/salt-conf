postgresql_jupyterhub_container:
  radia.docker_container:
    - container_name: '{{ pillar.jupyterhub.postgresql_name }}'
    - cmd: postgres
    - guest_user: postgres
    - image_name: '{{ pillar.jupyterhub.postgresql_image }}'
    - init:
        env:
          - [ POSTGRES_PASSWORD, {{ pillar.postgresql_jupyterhub.admin_pass }} ]
          - [ JPY_PSQL_PASSWORD, {{ pillar.jupyterhub.db_pass }} ]
        cmd: bash /radia-init.sh
        sentinel: {{ pillar.jupyterhub.postgresql_host_data_d }}/PG_VERSION
    - ports:
      - [ 5432, 5432 ]
    - volumes:
      - [ '{{ pillar.jupyterhub.postgresql_host_data_d }}', /var/lib/postgresql/data ]
      - [ '{{ pillar.jupyterhub.postgresql_host_run_d }}', /run/postgresql ]

jupyter_singleuser_image:
  radia.docker_image:
    - image_name: '{{ pillar.jupyterhub.jupyter_singleuser_image }}'

jupyterhub_config:
  radia.plain_file:
    - file_name: '{{ pillar.jupyterhub.host_conf_f }}'
    - contents_pillar: jupyterhub:conf_contents
    - user: root
    - group: root
    - zz:
        jupyter_image: '{{ pillar.jupyterhub.jupyter_singleuser_image }}'

{% if pillar.jupyterhub.nfs_local_d %}
jupyterhub_nfs:
  radia.nfs_mount:
    - local_dir: '{{ pillar.jupyterhub.nfs_local_d }}'
    - remote_dir: '{{ pillar.jupyterhub.nfs_remote_d }}'
{% endif %}

jupyterhub_container:
  radia.docker_container:
    - after:
        - {{ pillar.jupyterhub.postgresql_name }}
    - container_name: jupyterhub
    - cmd: jupyterhub -f '{{ pillar.jupyterhub.guest_conf_f }}'
    - image_name: '{{ pillar.jupyterhub.image_name }}'
    - guest_user: {{ pillar.jupyterhub.guest_user }}
    - host_user: {{ pillar.jupyterhub.host_user }}
    - links:
        - {{ pillar.jupyterhub.postgresql_name }}
    - ports:
        - [ {{ pillar.jupyterhub.host_port }}, {{ pillar.jupyterhub.guest_port }} ]
    - volumes:
        - [ {{ pillar.jupyterhub.host_conf_d }}, {{ pillar.jupyterhub.guest_conf_d }} ]
        {% if pillar.jupyterhub.nfs_local_d %}
        - [ {{ pillar.jupyterhub.nfs_local_d }}, {{ pillar.jupyterhub.nfs_local_d }} ]
        {% endif %}
    - want_docker_sock: True

# Needed for vagrant
# timedatectl set-ntp yes
