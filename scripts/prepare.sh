#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
env_dir="$root/.im2015"
packages=${1:-"$env_dir/packages"}
python -c 'import sys; assert sys.version_info[:2] == (2, 7)'
mkdir -p "$env_dir"/{deps,lib,pox}

cd "$packages"
sha256sum -c "$root/data/dependencies.sha256"
for package in ovs-common ovs-switch mininet; do
    dpkg-deb -x "$package.deb" "$env_dir/deps"
done
for package in nx decorator; do
    tar -xzf "$package.tar.gz" -C "$env_dir/lib"
done
tar -xzf pox.tar.gz --strip-components=1 -C "$env_dir/pox"

# Modern Linux kernels may show a veth name as eth0@ifN.
python - "$env_dir/deps/usr/lib/python2.7/dist-packages/mininet/util.py" <<'PY'
import sys

path = sys.argv[1]
old = "if not ( ' %s:' % intf ) in links:"
new = "if not ( ' %s:' % intf ) in links and not ( ' %s@' % intf ) in links:"
with open(path) as stream:
    source = stream.read()
assert source.count(old) == 1
with open(path, "w") as stream:
    stream.write(source.replace(old, new))
PY
