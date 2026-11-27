# YoruGram Android Foundation

Unofficial Telegram Android fork. The upstream GPL license and notices remain in place. This branch includes a YoruGram settings screen, a localized wallpaper gallery with PNG export, and a shortcut to Telegram's built-in proxy configuration.

## Build and install the offline APK

Install JDK 17, Android SDK Platform 36, Build Tools 36.0.0, NDK 27.2.12479018, and CMake 3.22.1. Clone `yoru/foundation` and its submodules. Open the repository root as a project in Android Studio or use the same root in VS Code.

```sh
git submodule update --init --recursive --depth 1
bash gradlew --no-daemon -PyoruOfflineSmoke=true :TMessagesProj_AppStandalone:assembleAfatDebug
adb install -r TMessagesProj_AppStandalone/build/outputs/apk/afat/debug/app.apk
```

Use a clean checkout for this build. Its Android package is `org.yorugram.messenger.web.smoke`. This build uses the Android debug key and includes ARM64, ARMv7 and x86_64 libraries. It has no Internet permission and uses no Telegram or Firebase credentials. Use it for installation and local interface checks. Sign-in, messaging, push delivery, and proxy connectivity require the project API build.

Pushing to `yoru/foundation` builds the offline variant in GitHub Actions. CI verifies the APK signature, package, Internet permission and native libraries before uploading the artifact as `YoruGram-Offline-Test.apk`.

The workflow also installs the APK on an Android 35 x86_64 emulator, opens the launcher activity, and checks that YoruGram stays in the foreground before capturing the screen.

## Build with project credentials

1. Register the app at [my.telegram.org](https://my.telegram.org/) and use the API ID and hash issued to this project.
2. In your Firebase project, register the Android app `org.yorugram.messenger.web` and download its `google-services.json`. Enable Firebase Cloud Messaging to test push delivery.
3. In a disposable checkout, provide `YORU_API_ID`, `YORU_API_HASH` and `YORU_FIREBASE_JSON` as environment variables, with the full JSON contents in the last variable. Run `python3 yoru-build/configure.py` from the repository root. It configures the standalone debug variant and replaces the local API placeholders in `BuildVars.java`.
4. Run `bash gradlew --no-daemon :TMessagesProj_AppStandalone:assembleAfatDebug`. Install the resulting debug APK with `adb install -r`. Keep the same local debug key when testing APK updates.

For CI, set the same names as [repository secrets](https://github.com/giova355/YoruGram-Android/settings/secrets/actions) and select **Build with the project's Telegram API and Firebase configuration** when manually starting the workflow. CI compiles this variant on a public fork and uploads its APK only in a private repository. Keep the configured Java source, Firebase files, and signing keys out of commits. Use your own stable signing key for a production release.

The Windows companion is [YoruGram Desktop](https://github.com/giova355/YoruGram-Desktop/tree/yoru/foundation).
