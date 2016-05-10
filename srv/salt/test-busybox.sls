
busybox_container:
  bivio.docker_container:
    - container_name: busybox
    - image_name: "busybox:latest"
    - cmd: sleep 1000
    - guest_user: ''
    - volumes:
        - [ /tmp/foo, /foo ]
    - ports:
        - [ 5692, 5692 ]
    - env:
        - [ xyz, abc ]
    - init:
        cmd: "/bin/sh -c 'echo $big_secret > /foo/key'"
        env:
          - [ big_secret, s3cr3t ]
        sentinel: /tmp/foo/key


#    - ports: 5555
#    - user: ''
#    - volumes:
#        - [ /var/tmp /foo ]

#id1:
#  btest.t1:
#    - other: foo
#
#id2:
#  btest.t2:
#    - require:
#      - btest.id1
