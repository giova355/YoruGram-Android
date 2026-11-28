#!/usr/bin/env bash
set -euo pipefail

sdk=${1:?Provide the SDK directory}
shift
tools="$sdk/cmdline-tools/latest/bin"
if [[ ! -x "$tools/sdkmanager" ]]; then
    archive=$(mktemp)
    trap 'rm -f "$archive"' EXIT
    curl --fail --silent --show-error --retry 3 \
        https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
        -o "$archive"
    printf '%s  %s\n' 7ec965280a073311c339e571cd5de778b9975026cfcbe79f2b1cdcb1e15317ee "$archive" | sha256sum --check
    mkdir -p "$sdk/cmdline-tools"
    unzip -q "$archive" -d "$sdk/cmdline-tools"
    mv "$sdk/cmdline-tools/cmdline-tools" "$sdk/cmdline-tools/latest"
fi
"$tools/sdkmanager" --sdk_root="$sdk" --licenses < <(yes)
"$tools/sdkmanager" --sdk_root="$sdk" "$@"
