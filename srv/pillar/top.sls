base:
  '*':
    - {{ grains.fqdn|replace(".", "_") }}
