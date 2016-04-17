#!/bin/bash
set -e
if [[ ! -b /dev/sda ]]; then
    echo 'No /dev/sda'
    exit 1
fi
if [[ ! -b /dev/sda3 ]]; then
    #TODO(robnagler) let it extend root lvm
    parted /dev/sda \
	mkpart primary ext2 113248256s 1952448511s \
	set 3 lvm on < /dev/null
    echo 'parted: /dev/sda3'
fi
if ! pvck /dev/sda3 >& /dev/null; then
    pvcreate /dev/sda3
    echo 'pvcreate: /dev/sda3'
fi
if ! vgck docker >& /dev/null; then
    vgcreate docker /dev/sda3
    echo 'vgcreate: docker'
fi
if [[ ! -b /dev/mapper/docker-docker--pool ]]; then
    VG=docker docker-storage-setup
    echo 'docker-storage-setup'
fi
