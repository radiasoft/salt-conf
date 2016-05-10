{%
    set zz = dict(
        juypter_singleuser_image='radiasoft/jupyter:' + pillar.pykern_channel,
        jupyterhub_host_conf_d='/var/lib/jupyterhub/conf',
        postgresql_home_d='/var/lib/postgresql-jupyterhub',
        jupyterhub_guest_conf_d='/srv/jupyterhub/conf',
        jupyterhub_config_f='jupyterhub_config.py',
    )
    zz['postgresql_data_d'] = zz['postgresql_home_d'] + '/data'

%}

base_pkgs:
  bivio.pkg_installed:
    pkgs:
      - docker
      - emacs-nox
      - lsof
      - screen
      - tar
      - telnet

postgresql_jupyterhub_container:
  bivio.docker_container:
    - container_name: postgresql_jupyterhub
    - image_name: radiasoft/postgresql-jupyterhub
    - volumes:
      - [ {{ zz.postgresql_data_d }}, /var/lib/postgresql/data ]]
      - [ {{ zz.postgresql_home_d }}/run, /run/postgresql ]
    - user: postgres
    - ports:
      - [ 5432 5432 ]
    - init:
      env:
        - [ POSTGRES_PASSWORD, {{ postgresql.admin_pass }} ]
        - [ JPY_PSQL_PASSWORD, {{ jupyterhub.db_pass }} ]
      cmd: /radia-init.sh
      sentinel: {{ zz.postgresql_data_d }}/PG_VERSION

jupyter_singleuser_image:
  bivio.docker_image:
    - image_name: {{ zz.jupyter_singleuser_image }}

jupyterhub_config:
  bivio.plain_file:
    - file_name: {{ zz.jupyterhub_host_conf_d }}/{{ zz.jupyterhub_config_f }}
    - contents_pillar: {{ pillar.jupyterhub.config_contents }}
    - zz:
        jupyter_image: {{ zz.jupyter_singleuser_image }}

jupyterhub_container:
  bivio.docker_container:
    - container_name: jupyterhub
    - image_name: radiasoft/jupyterhub
    - links:
        - postgresql_jupyterhub
    - want_docker_sock: True
    - volumes:
        - [ {{ zz.jupyterhub_host_conf_d }}, {{ zz.jupyterhub_guest_conf_d }} ]
    - user: root
    - ports:
        - [ 5692, 8000 ]
    - cmd: jupyterhub -f {{ zz.jupyterhub_guest_conf_d }}/{{ zz.jupyterhub_config_f }}
    - after:
        - postgresql
    - require:
        - bivio.postgresql_jupyterhub_container
        - bivio.jupyter_singleuser_image
        - bivio.jupyterhub_config
