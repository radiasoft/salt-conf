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
    - init:
        env:
          - [ POSTGRES_PASSWORD {{ postgresql.pass }} ]
          - [ JPY_PSQL_PASSWORD {{ jupyterhub.db_pass }} ]
        user: None
        sentinel: /var/lib/postgresql/data/PG_VERSION
    - user: postgres
    - ports: [ 5432 ]


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
    - volumes:
        - [ /var/lib/jupyterhub/conf /srv/jupyterhub/conf ]
    - user: root
    - dockersock: True
    - ports:
        - [ 5692 8000 ]
    - cmd: jupyterhub -f /srv/jupyterhub/conf/jupyter_config.py
    - require:
        - postgresql
        - jupyter_singleuser
        - jupyterhub_config
