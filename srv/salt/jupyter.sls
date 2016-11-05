jupyter_image:
  radia.docker_image:
    - image_name: '{{ pillar.jupyter.image_name }}'

jupyter_notebook_nfs:
  radia.nfs_mount:
    - local_dir: '{{ pillar.jupyter.notebook_local_d }}'
    - remote_dir: '{{ pillar.jupyter.notebook_remote_d }}'
    - user: '{{ pillar.jupyter.host_user }}'
    - group: '{{ pillar.jupyter.guest_user }}'
    - dir_mode: 700
