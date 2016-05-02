postgresql_image:
  bivio.docker_image:
    - image: radiasoft/postgresql

postgresql:
  bivio.docker_container:
# channel is implicit -- machine is always on one channel
    - image: radiasoft/postgresql
    - volumes:
      - [ /var/lib/postgresql /var/lib/postgresql ]
      - [ /var/lib/postgresql/run /run/postgresql ]
    - user: postgres
    - ports:
      - [ 5432 5432 ]
    - init:
      env:
        - [ POSTGRES_PASSWORD {{ postgresql.pass }} ]
        - [ JPY_PSQL_PASSWORD {{ jupyterhub.db_pass }} ]
      user: None
      sentinel: /var/lib/postgresql/data/PG_VERSION

docker_sock_semodule:
  bivio.docker_sock_semodule: []


jupyter_singleuser:
  bivio.docker_image:
    - name: radiasoft/jupyter-singleuser


jupyterhub_config:
  bivio.plain_file:
    - name: /var/lib/jupyterhub/conf/jupyterhub_config.py
    - user: {{ pillar.docker_user }}


jupyterhub:
  bivio.docker_container:
    - image: radiasoft/jupyterhub
    - links:
        - postgresql
    - docker_sock: True
    - volumes:
        - [ /var/lib/jupyterhub/conf /srv/jupyterhub/conf ]
    - user: root
    - ports:
        - [ 5692 8000 ]
    - cmd: jupyterhub -f /srv/jupyterhub/conf/jupyter_config.py
    - after:
        - postgresql
    - require:
        - bivio.postgresql
        - bivio.jupyter_singleuser
        - bivio.jupyterhub_config
        - bivio.docker_sock_semodule
