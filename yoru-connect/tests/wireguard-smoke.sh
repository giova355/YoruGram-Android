#!/usr/bin/env bash
set -euo pipefail

python=${1:?Provide an absolute path to Python}
state=$(mktemp -d)
cleanup() {
    ip netns del yoru-test-server 2>/dev/null || true
    ip netns del yoru-test-client 2>/dev/null || true
    rm -rf "$state"
}
trap cleanup EXIT
umask 077

ip netns add yoru-test-server
ip netns add yoru-test-client
ip link add yoru-server0 type veth peer name yoru-client0
ip link set yoru-server0 netns yoru-test-server
ip link set yoru-client0 netns yoru-test-client
server_ip() { ip -n yoru-test-server "$@"; }
client_ip() { ip -n yoru-test-client "$@"; }
server() { ip netns exec yoru-test-server "$@"; }
client() { ip netns exec yoru-test-client "$@"; }

server_ip link set lo up
client_ip link set lo up
server_ip addr add 192.0.2.1/30 dev yoru-server0
client_ip addr add 192.0.2.2/30 dev yoru-client0
server_ip link set yoru-server0 up
client_ip link set yoru-client0 up
server_ip link add wg-yoru type wireguard
client_ip link add wg-yoru type wireguard
server_ip addr add 10.70.0.1/24 dev wg-yoru
server_ip addr add fd70:7952:7500::1/64 dev wg-yoru nodad
client_ip addr add 10.70.0.2/24 dev wg-yoru
client_ip addr add fd70:7952:7500::2/64 dev wg-yoru nodad
server_ip link set wg-yoru up
client_ip link set wg-yoru up

wg genkey > "$state/server.key"
wg genkey > "$state/client.key"
client_public=$(wg pubkey < "$state/client.key")
export YORU_DB="$state/state.sqlite3" YORU_ENDPOINT="192.0.2.1:51820" YORU_DNS="10.70.0.1"
export YORU_REGION="CI" YORU_PRIVATE_KEY_FILE="$state/server.key"
YORU_SERVER_PUBLIC_KEY=$(wg pubkey < "$state/server.key")
export YORU_SERVER_PUBLIC_KEY
"$python" - "$client_public" <<'PY'
from pathlib import Path
import os
import sys
import time
from yoru_connect.storage import Store, token_digest
store = Store(Path(os.environ["YORU_DB"]))
store.initialize()
token = token_digest(store.create_account("test-user"))
now = int(time.time())
store.start_trial(token, now)
store.enroll(token, sys.argv[1], now)
PY
server "$python" -m yoru_connect.admin reconcile --runtime-directory "$state"
cat "$state/client.key" | client wg set wg-yoru private-key /dev/stdin peer "$YORU_SERVER_PUBLIC_KEY" \
    endpoint "$YORU_ENDPOINT" allowed-ips '10.70.0.1/32,fd70:7952:7500::1/128' persistent-keepalive 25
client ping -c 1 -w 10 10.70.0.1
client ping -6 -c 1 -w 10 fd70:7952:7500::1
client wg show wg-yoru latest-handshakes | awk 'NF == 2 && $2 > 0 {found=1} END {exit !found}'
"$python" -m yoru_connect.admin disable test-user
server "$python" -m yoru_connect.admin reconcile --runtime-directory "$state"
test -z "$(server wg show wg-yoru peers)"
printf '%s\n' 'WireGuard IPv4/IPv6 handshake, packets and peer revocation verified.'
