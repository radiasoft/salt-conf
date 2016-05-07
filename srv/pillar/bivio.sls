bivio:
  mod_init:
    inventory: '/var/lib/bivio-salt/inventory/{now}.yml'

  dockersock:
    policy: dockersock

  docker_container:
    user: vagrant
    sock: /run/docker.sock
    program: /usr/bin/docker
    stop_time: 2
    systemd:
      filename: '/etc/systemd/system/{name}.service'
{% raw %}
      contents: |
        [Unit]
        Description={{ zz.name }}
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

  docker_sock_semodule:
    name: bivio_docker_sock
{% raw %}
    contents: |
      module {{ pillar.bivio.docker_sock_semodule.name }} 1.0;
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

  plain_file:
    source: "salt://./{name}"
    defaults:
      dir_mode: "750"
      group: "{{ grains.username }}"
      makedirs: True
      mode: "440"
      template: jinja
      user: "{{ grains.username }}"
