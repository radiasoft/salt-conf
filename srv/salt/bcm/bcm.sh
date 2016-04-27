#!/bin/bash
#
#

set -e
bcm_lib=$(dirname ${BASH_SOURCE[0]})
eval $(python $bcm_lib/bcm_vars.py grains)
eval $(python $bcm_lib/bcm_vars.py pillar)
printf '{"changed":"yes", "comment":"%s"}' "host is $grains_fqdn"
