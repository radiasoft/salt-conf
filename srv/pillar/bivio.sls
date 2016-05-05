{% raw %}
bivio:
  mod_init:
    inventory: '/var/lib/bivio-salt/inventory/{now}.yml'

  dockersock:
    policy: dockersock

  docker_container:
    docker_sock: /run/docker.sock
    user: vagrant
    systemd:
      filename: '/etc/systemd/system/{name}.service'
      contents: |
        [Unit]
        Description={{ zz.name }}
        Requires={{ zz.after }}
        After={{ zz.after }}

        [Service]
        Restart=on-failure
        RestartSec=10
        # The :Z sets the selinux context to the appropriate
        # Multi-Category Security (MCS)
        # http://www.projectatomic.io/blog/2015/06/using-volumes-with-docker-can-cause-problems-with-selinux/
        ExecStart=/usr/bin/docker run -t --rm{{ zz.args }}
        ExecStop=-/usr/bin/docker stop -t 2 {{ zz.name }}

        [Install]
        WantedBy=multi-user.target

  docker_sock_semodule:
    name: bivio_docker_sock
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

  plain_file:
    source: "salt://./{name}"
    defaults:
      dir_mode: "750"
      group: "{{ grains.username }}"
      makedirs: True
      mode: "440"
      template: jinja
      user: "{{ grains.username }}"
{% endraw %}
