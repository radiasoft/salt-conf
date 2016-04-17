# Called from etc/master
sync-all:
  local.saltutil.sync_all:
    - tgt: {{ data['id'] }}
