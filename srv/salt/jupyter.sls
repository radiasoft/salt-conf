jupyter_image:
  radia.docker_image:
    - image_name: '{{ pillar.jupyter.image_name }}'

{% if pillar.jupyter.nfs_local_d %}
jupyter_nfs:
  radia.nfs_mount:
    - local_dir: '{{ pillar.jupyter.nfs_local_d }}'
    - remote_dir: '{{ pillar.jupyter.nfs_remote_d }}'
    - user: '{{ pillar.jupyter.host_user }}'
    - group: '{{ pillar.jupyter.guest_user }}'
    - mode: 700
{% endif %}
