#!/bin/bash
#
# Initialize Certificate Authority
#
if (( $# == 0 )); then
    echo "usage: bash $0 server-ip/host..." 1>&2
    exit 1
fi

cd "$(dirname $0)/.."
mkdir -p docker-tls
cd docker-tls
if [[ ! -f ca.crt ]]; then
    if [[ ! -f ca.key ]]; then
        openssl genrsa -out ca.key 4096
    fi
    openssl req -new -subj "/CN=ca" -x509 -days 9999 -key ca.key -out ca.crt
fi

create_yml() {
    local pillar=$1
    local host=$2
    local ext=$3
    local d="../srv/pillar/secrets/docker-tls"
    local yml="$d/$host.yml"
    if [[ -f $yml ]]; then
        return
    fi
    mkdir -p "$d"
    openssl genrsa -out "$host.key" 4096
    openssl req -subj "/CN=$host" -sha256 -new -key "$host.key" -out "$host.csr"
    echo "$ext" > "$host.cfg"
    openssl x509 -req -days 9999 -sha256 -in "$host.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -out "$host.crt" -extfile "$host.cfg"
    rm -f "$host.csr" "$host.cfg"
    python - <<EOF > "$yml"
from __future__ import print_function
import re

print('radia:\n  $pillar:')
for k, f in ('tlskey', '$host.key'), ('tlscacert', 'ca.crt'), ('tlscert', '$host.crt'):
    print('    {}: |'.format(k))
    print(re.sub('^', '      ', open(f).read(), flags=re.MULTILINE))
EOF
    echo "Created: $yml"
}

for host in "$@"; do
    ip=$(dig "$host" +short)
    if [[ $ip == $host ]]; then
        # Should only be used for testing
        host=server
    fi
    create_yml docker_service "$host" "subjectAltName = IP:$ip,IP:127.0.0.1"
done

create_yml docker_master_client docker-master-client 'extendedKeyUsage = clientAuth'
