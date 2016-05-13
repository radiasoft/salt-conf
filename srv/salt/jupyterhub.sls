{% set zz = dict(
    jupyter_singleuser_image='radiasoft/beamsim-jupyter:' + pillar.pykern.channel,
    jupyterhub_config_f='jupyterhub_config.py',
    jupyterhub_guest_conf_d='/srv/jupyterhub/conf',
    jupyterhub_host_conf_d='/var/lib/jupyterhub/conf',
    jupyterhub_user='root',
    postgresql_name='postgresql-jupyterhub'
) %}
{% set _dummy = zz.update(
    postgresql_home_d='/var/lib/' + zz.postgresql_name,
) %}
{% set _dummy = zz.update(
    postgresql_data_d=zz.postgresql_home_d + '/data',
) %}

postgresql_jupyterhub_container:
  bivio.docker_container:
    - container_name: {{ zz.postgresql_name }}
    - cmd: postgres
    - guest_user: postgres
    - image_name: radiasoft/{{ zz.postgresql_name }}
    - init:
        env:
          - [ POSTGRES_PASSWORD, {{ pillar.postgresql_jupyterhub.admin_pass }} ]
          - [ JPY_PSQL_PASSWORD, {{ pillar.jupyterhub.db_pass }} ]
        cmd: bash /radia-init.sh
        sentinel: {{ zz.postgresql_data_d }}/PG_VERSION
    - ports:
      - [ 5432, 5432 ]
    - volumes:
      - [ {{ zz.postgresql_data_d }}, /var/lib/postgresql/data ]
      - [ {{ zz.postgresql_home_d }}/run, /run/postgresql ]

jupyter_singleuser_image:
  bivio.docker_image:
    - image_name: {{ zz.jupyter_singleuser_image }}

jupyterhub_config:
  bivio.plain_file:
    - file_name: {{ zz.jupyterhub_host_conf_d }}/{{ zz.jupyterhub_config_f }}
    - contents_pillar: jupyterhub:config_contents
    - user: root
    - group: root
    - zz:
        jupyter_image: {{ zz.jupyter_singleuser_image }}

jupyterhub_container:
  bivio.docker_container:
    - after:
        - {{ zz.postgresql_name }}
    - container_name: jupyterhub
    - cmd: jupyterhub -f {{ zz.jupyterhub_guest_conf_d }}/{{ zz.jupyterhub_config_f }}
    - image_name: radiasoft/jupyterhub
    - guest_user: {{ zz.jupyterhub_user }}
    - host_user: {{ zz.jupyterhub_user }}
    - links:
        - {{ zz.postgresql_name }}
    - ports:
        - [ {{ pillar.jupyterhub.host_port }}, 8000 ]
    - volumes:
        - [ {{ zz.jupyterhub_host_conf_d }}, {{ zz.jupyterhub_guest_conf_d }} ]
    - want_docker_sock: True

# Needed for vagrant
# timedatectl set-ntp yes
