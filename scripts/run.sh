#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
env_dir="$root/.im2015"
name=${1:?Supply a name for the run directory}
case "$name" in (*[!a-zA-Z0-9-]*|'') exit 2;; esac
shift
if [[ $# -eq 1 && $1 =~ ^([1-9]|[1-3][0-9]|40)$ ]]; then
    set -- --cycles "$1"
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 NAME [CYCLES (1–40)]" >&2
    exit 2
fi
if [[ $EUID -ne 0 ]]; then
    echo "Run as root inside the dedicated Linux guest." >&2
    exit 1
fi
if [[ ! -f "$env_dir/pox/pox.py" ]]; then
    echo "Prepare the dependencies with scripts/prepare.sh first." >&2
    exit 1
fi

export PATH="$env_dir/deps/usr/bin:$env_dir/deps/usr/sbin:$PATH"
export PYTHONPATH="$env_dir/deps/usr/lib/python2.7/dist-packages:$env_dir/lib/networkx-1.8.1:$env_dir/lib/decorator-3.4.0/src"
export PYTHONDONTWRITEBYTECODE=1
out="$root/runs/$name"
ovs_run=/var/run/openvswitch
mkdir -p "$root/runs" "$ovs_run"
exec 9>"$ovs_run/im2015.lock"
flock -n 9
for file in db.sock ovs-vswitchd.pid ovsdb-server.pid; do
    if [[ -e "$ovs_run/$file" ]]; then
        echo "Open vSwitch is already present. Use a dedicated guest." >&2
        exit 1
    fi
done
mkdir "$out"
cp "$root/code/graphcontrol.py" "$env_dir/pox/ext/"

cleanup() {
    for pidfile in "$ovs_run"/{ovs-vswitchd,ovsdb-server}.pid; do
        if [[ -f "$pidfile" ]]; then
            kill "$(cat "$pidfile")" || true
        fi
    done
}
trap cleanup EXIT
ovsdb-tool create "$out/conf.db" "$env_dir/deps/usr/share/openvswitch/vswitch.ovsschema"
ovsdb-server "$out/conf.db" --remote="punix:$ovs_run/db.sock" \
    --pidfile="$ovs_run/ovsdb-server.pid" --detach 9>&-
ovs-vsctl --no-wait init
ovs-vswitchd "unix:$ovs_run/db.sock" --pidfile="$ovs_run/ovs-vswitchd.pid" --detach 9>&-
for scenario in baseline multipath; do
    python -u "$root/scripts/run_experiment.py" "$scenario" "$out/$scenario" --home "$env_dir" "$@"
done
