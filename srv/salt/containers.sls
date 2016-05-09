base_pkgs:
  bivio.pkg_installed:
    pkgs:
      - docker
      - emacs-nox
      - lsof
      - screen
      - tar
      - telnet

postgresql_container:
  bivio.docker_container:
    - container_name: postgresql
    - image_name: radiasoft/postgres
    - volumes:
      - /var/lib/postgresql/data
      - [ /var/lib/postgresql/run, /run/postgresql ]
    - user: postgres
    - ports:
      - [ 5432 5432 ]
    - init:
      env:
        - [ POSTGRES_PASSWORD, {{ postgres.admin_pass }} ]
        - [ JPY_PSQL_PASSWORD, {{ jupyterhub.db_pass }} ]
      cmd: /radia-init.sh
      sentinel: /var/lib/postgresql/data/PG_VERSION

jupyter_singleuser:
  bivio.docker_image:
    - name: radiasoft/jupyter-singleuser

jupyterhub_config:
  bivio.plain_file:
    - name: /var/lib/jupyterhub/conf/jupyterhub_config.py
    - user: {{ pillar.docker_container_user }}

jupyterhub:
  bivio.docker_container:
    - image: radiasoft/jupyterhub
    - links:
        - postgresql
    - want_docker_sock: True
    - volumes:
        - [ /var/lib/jupyterhub/conf, /srv/jupyterhub/conf ]
    - user: root
    - ports:
        - [ 5692, 8000 ]
    - cmd: jupyterhub -f /srv/jupyterhub/conf/jupyter_config.py
    - after:
        - postgresql
    - require:
        - bivio.postgresql
        - bivio.jupyter_singleuser
        - bivio.jupyterhub_config
