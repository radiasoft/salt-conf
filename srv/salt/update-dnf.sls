# There was a bug in dnf, which caused salt to not see package list.
# The fix was to update dnf and dnf-plugins-core. However, you
# can't sat pkg.latest, because it didn't see dnf so it tried to
# reintall it. Therefore we just have to run this command
update-dnf:
  cmd.run:
    - name: dnf -y update dnf dnf-plugins-core
