#
# TODO(robnagler) configure backups for postgres
#
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

jupyterhub_config:
  radia.plain_file:
    - file_name: '{{ pillar.jupyterhub.host_conf_f }}'
    - source: salt://jupyterhub/jupyterhub_config.py
    - user: root
    - group: root
    - zz:
        jupyter_image: '{{ pillar.jupyter.image_name }}'

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
        - [ {{ pillar.jupyter.nfs_local_d }}, {{ pillar.jupyter.nfs_local_d }} ]
    - want_docker_sock: True
    - watch:
        - jupyterhub_config
