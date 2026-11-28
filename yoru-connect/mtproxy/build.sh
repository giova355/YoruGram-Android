#!/usr/bin/env bash
set -euo pipefail

revision=96cfd2faeeb6f0c98a79b5d2c5f1dc94fdff3806
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $# != 1 || $(uname -sm) != 'Linux x86_64' ]]; then
  echo 'Usage on Linux x86-64: bash build.sh OUTPUT_DIRECTORY' >&2
  exit 2
fi
mkdir -p -- "$1"
output=$(cd -- "$1" && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT

git -C "$work" init -q
git -C "$work" fetch -q --depth=1 https://github.com/TelegramMessenger/MTProxy.git "$revision"
git -C "$work" checkout -q --detach FETCH_HEAD
test "$(git -C "$work" rev-parse HEAD)" = "$revision"
git -C "$work" apply "$source_dir/client-secret-file.patch"
make -s -C "$work" -j "${JOBS:-2}"

install -m 0755 "$work/objs/bin/mtproto-proxy" "$output/mtproto-proxy"
tar -C "$work" --exclude=.git --exclude=dep --exclude=objs -czf "$output/MTProxy-source.tar.gz" .
printf '%s\n' "$revision" > "$output/upstream-revision"
