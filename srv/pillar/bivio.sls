{% set zz = dict(
    user='vagrant',
    file_mode='400',
    dir_mode='700',
    docker_group='docker',
    docker_sock='/run/docker.sock',
) %}

bivio:
  docker:
    service_name: docker

  docker_container:
    host_user: "{{ zz.user }}"
    guest_user: "{{ zz.user }}"
    sock: "{{ zz.docker_sock }}"
    program: /usr/bin/docker
    stop_time: 2
    makedirs: True
    systemd_filename: '/etc/systemd/system/{service_name}.service'
{% raw %}
    systemd_contents: |
        [Unit]
        Description={{ zz.service_name }}
        Requires={{ zz.after }}
        After={{ zz.after }}

        [Service]
        Restart=on-failure
        RestartSec=10
        ExecStartPre=-{{ zz.remove }}
        ExecStart={{ zz.start }}
        ExecStop=-{{ zz.stop }}

        [Install]
        WantedBy=multi-user.target
{% endraw %}

  docker_image: {}

  docker_service:
    sock: "{{ zz.docker_sock }}"
    sock_group: "{{ zz.docker_group }}"
    required_pkgs:
      - docker
      - lvm2

  docker_sock_semodule:
    policy_name: bivio_docker_sock
{% raw %}
    contents: |
      module {{ zz.policy_name }} 1.0;
      require {
          type docker_var_run_t;
          type docker_t;
          type svirt_lxc_net_t;
          class sock_file write;
          class unix_stream_socket connectto;
      }
      allow svirt_lxc_net_t docker_t:unix_stream_socket connectto;
      allow svirt_lxc_net_t docker_var_run_t:sock_file write;
{% endraw %}

  host_user:
    docker_gid: 496
    docker_group: "{{ zz.docker_group }}"
    uid: 1000
    user_name: "{{ zz.user }}"
    want_docker_sock: True

  mod_init:
    inventory: '/var/lib/bivio-salt/inventory/{now}.yml'

  plain_directory:
    dir_mode: "{{ zz.dir_mode }}"
    file_mode: "{{ zz.file_mode }}"
    group: "{{ zz.user }}"
    makedirs: True
    user: "{{ zz.user }}"

  plain_file:
    dir_mode: "{{ zz.dir_mode }}"
    group: "{{ zz.user }}"
    makedirs: True
    mode: "{{ zz.file_mode }}"
    template: jinja
    user: "{{ zz.user }}"

  pkg_installed: {}
