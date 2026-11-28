#!/usr/bin/env bash
set -euo pipefail

apk=${1:?Provide the test APK}
screenshot=${2:?Provide an output path for the screenshot}
sdk=${ANDROID_HOME:?Set ANDROID_HOME}
runner_temp=${RUNNER_TEMP:-${TMPDIR:-/tmp}}
tools="$sdk/cmdline-tools/latest/bin"
adb="$sdk/platform-tools/adb"
emulator="$sdk/emulator/emulator"
image='system-images;android-35;google_apis;x86_64'

export ANDROID_USER_HOME="$runner_temp/yoru-android-user"
export ANDROID_EMULATOR_HOME="$ANDROID_USER_HOME"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
mkdir -p "$ANDROID_AVD_HOME" "$(dirname "$screenshot")"
"$tools/avdmanager" create avd --force --name yoru-smoke --package "$image" \
    --path "$ANDROID_AVD_HOME/yoru-smoke.avd" <<< no
test -f "$ANDROID_AVD_HOME/yoru-smoke.ini"
"$emulator" -list-avds | grep -Fx yoru-smoke

acceleration=off
if [[ -e /dev/kvm ]]; then
    if [[ ! -w /dev/kvm && "${GITHUB_ACTIONS:-false}" == true ]]; then
        sudo chown "$(id -u):$(id -g)" /dev/kvm
    fi
    if [[ -r /dev/kvm && -w /dev/kvm ]]; then
        acceleration=on
    fi
fi
log="$runner_temp/yoru-emulator.log"
"$emulator" -avd yoru-smoke -no-window -no-audio -no-snapshot \
    -gpu swiftshader -accel "$acceleration" > "$log" 2>&1 &
emulator_pid=$!
trap 'kill "$emulator_pid" 2>/dev/null || true' EXIT

if ! timeout 300 "$adb" wait-for-device; then
    cat "$log"
    exit 1
fi
for ((attempt=0; attempt<150; attempt++)); do
    booted=$("$adb" shell getprop sys.boot_completed | tr -d '\r')
    [[ "$booted" == 1 ]] && break
    sleep 2
done
if [[ "$booted" != 1 ]]; then
    cat "$log"
    exit 1
fi

"$adb" shell input keyevent KEYCODE_WAKEUP
"$adb" shell wm dismiss-keyguard
"$adb" install -g "$apk"
package=org.yorugram.messenger.web.smoke
"$adb" shell am start -W -n "$package/org.telegram.messenger.DefaultIcon"
sleep 5
if ! "$adb" shell pidof "$package" ||
    [[ $("$adb" shell dumpsys activity activities | sed -n '/topResumedActivity=/p') != *"$package/"* ]]; then
    "$adb" logcat -d -s AndroidRuntime
    exit 1
fi
if [[ "${YORU_EXPECT_BRAND:-false}" == true ]]; then
    "$adb" shell uiautomator dump /sdcard/yoru-intro.xml
    "$adb" shell cat /sdcard/yoru-intro.xml | grep -F 'text="YoruGram"'
fi
"$adb" exec-out screencap -p > "$screenshot"
test -s "$screenshot"
