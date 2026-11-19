#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
downloads=${1:-"$root/.im2015/packages"}
mkdir -p "$downloads"
cd "$downloads"

download() {
    curl -fLsS --retry 1 --connect-timeout 8 --max-time 60 "$2" -o "$1"
}

download_ubuntu() {
    local mirror
    for mirror in https://ftp.ubuntu.com/ubuntu https://mirrors.edge.kernel.org/ubuntu https://archive.ubuntu.com/ubuntu https://old-releases.ubuntu.com/ubuntu; do
        if download "$1" "$mirror/$2"; then
            return
        fi
    done
    return 1
}

ovs=pool/main/o/openvswitch
version=2.0.1+git20140120-0ubuntu2
download_ubuntu ovs-common.deb "$ovs/openvswitch-common_${version}_amd64.deb"
download_ubuntu ovs-switch.deb "$ovs/openvswitch-switch_${version}_amd64.deb"
download_ubuntu mininet.deb pool/universe/m/mininet/mininet_2.1.0-0ubuntu1_amd64.deb
download pox.tar.gz https://codeload.github.com/noxrepo/pox/tar.gz/3b3fb43f0dac617d796bc5a18339ad79996bb6ba
download nx.tar.gz https://files.pythonhosted.org/packages/1e/ce/c5f0d432ab38b114a18020c1f716e08347b580b6865111ef1314995627a2/networkx-1.8.1.tar.gz
download decorator.tar.gz https://files.pythonhosted.org/packages/f3/26/876d492f2394f29401eb652ddfa53dec2bc8721861c7fe0dce1b5d0d2b6a/decorator-3.4.0.tar.gz
sha256sum -c "$root/data/dependencies.sha256"
