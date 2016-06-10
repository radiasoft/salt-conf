#!/bin/bash
#
# Polls for the file radia-mpi.sh for a specific owner.
# If the file is removed, the cluster stops. If the file
# is newer, the cluster (re)starts. If the uptime on the
# current host is below a threshold, the cluster is stopped.
#
set -e
load_avg_threshold=2
poll_secs=15

container_id() {
    docker inspect -f '{{ .Id }}' radia-mpi 2>/dev/null || true
}

container_running() {
    if [[ $(docker inspect --format='{{ .State.Running }}' radia-mpi 2>/dev/null) == true ]]; then
        log radia-mpi=running
        return 0
    fi
    log radia-mpi=stopped
    return 1
}

integer_load_avg() {
    local up=( $(uptime) )
    local res="${up[-1]%.*}"
    log "load=$res"
    echo $res
}

log() {
    echo "$(date +%H%M%S) $@" 1>&2
}

mpi_stop() {
    container_id=
    log mpi_stop
    salt-call -l quiet state.apply jupyter-mpi-stop pillar="{'username': '$owner', force: true}"
}

mpi_start() {
    script_mtime=$(script_mtime)
    log mpi_start "owner=$owner script_mtime=$script_mtime script=$script"
    salt-call -l quiet state.apply jupyter-mpi-start pillar="{'username': '$owner'}"
    container_id=$(container_id)
    log mpi_start "container_id=$container_id"
}

new_job() {
    (( $(script_mtime) > $script_mtime ))
    local ret=$?
    if (( $ret == 0 )); then
        log "new_job script_mtime=$(script_mtime)"
    fi
    return $ret
}

no_job() {
    if (( $(script_mtime) == 0 )); then
        log "no_job script gone"
        return 0
    fi
    return 1
}

processes_ok() {
    if ! container_running; then
        return 1
    fi
    local np=$(ps axww | grep -c ':[0-9][0-9] bash /home/vagrant/jupyter/radia-mpi.sh$')
    local x
    for x in $(seq 10); do
        # Must consume most of CPU. If a single MPI process gets a
        # SEGV, the whole cluster will block for that process at
        # the next "barrier". The cluster has to stop.
        #
        # This particular check assumes that there is a
        # radia-mpi-host (worker) container running on this host,
        # too. Really we should poll all nodes to see if all
        # are ok. This might be a config param, but seems
        # like either the job is keeping all nodes busy
        # or it's not doing what it's supposed to be doing.
        if (( $(integer_load_avg) > $np - $load_avg_threshold )); then
            return 0
        fi
        # HACK: need to poll this so we don't get locked in a loop
        if new_job || no_job; then
            return 0
        fi
        sleep 60
    done
    return 1
}

script_mtime() {
    stat -c %Y "$script" 2>/dev/null || echo 0
}

main() {
    owner=$1
    if [[ -z $owner ]]; then
        echo "usage: bash $0 <owner>" 1>&2
        exit 1
    fi
    owner_home=/var/db/jupyterhub/home/$owner
    script=$owner_home/radia-mpi.sh
    container_id=$(container_id)
    script_mtime=$(script_mtime)
    log "script_mtime=$script_mtime container_id=$container_id"
    while true; do
        sleep $poll_secs
        if [[ -n $container_id ]]; then
            if ! processes_ok || new_job || no_job; then
                mpi_stop
            else
                : log 'main: job running'
            fi
            continue
        fi
        if new_job; then
            mpi_stop
            mpi_start
        else
            : log 'main: no job'
        fi
    done
    # this way the rest of the script doesn't get read in the
    # case of editing it while it is running
    exit
}

main "$@"
