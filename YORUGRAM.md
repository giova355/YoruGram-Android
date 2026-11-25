# YoruGram 0.1.0 Foundation

Unofficial Telegram Android fork. The upstream GPL license and notices remain in place.

This branch integrates the independent YoruGram settings screen, localized wallpaper gallery, PNG export and a shortcut to the built-in Telegram proxy configuration. The included WebP resources are reduced-resolution versions of the Foundation artwork. Chat wallpaper application is still manual after export. Managed proxy servers, trial access, billing and owner entitlements are not implemented.

## Test build

Android SDK 36, NDK 27.2.12479018, CMake 3.22.1, Java 17 and recursive git submodules are required. Use your own Telegram API ID and hash from https://my.telegram.org, and your own Firebase project. Its google-services.json must include org.yorugram.messenger.web and the library namespace org.telegram.messenger. Set the environment variables YORU_API_ID, YORU_API_HASH and YORU_FIREBASE_JSON; run python3 yoru-build/configure.py in the repository root, replace the dummy release keystore with your own test key and configure signing properties before running:

```sh
bash gradlew --no-daemon :TMessagesProj_AppStandalone:assembleAfatDebug
```

Do not commit API credentials, Firebase files, signing keys or passwords. This is a private testing build only; the upstream debug configuration exposes diagnostic features. Production builds require a stable signing key and review of other upstream service credentials, package dependencies, branding, and licenses. Android build and runtime are not yet verified.

## Android CI setup

The first Actions run (45721658878) stopped at its configuration check because one or more required repository secrets were absent. No Gradle compilation took place.

1. Register your own application at https://my.telegram.org under API development tools.
2. Create a Firebase project and register Android apps for both `org.yorugram.messenger.web` and `org.telegram.messenger` (the upstream library namespace, not a second installed application). Download the updated configuration containing both client records.
3. Add repository Actions secrets `YORU_API_ID`, `YORU_API_HASH`, and `YORU_FIREBASE_JSON` (complete JSON text) at https://github.com/giova355/YoruGram-Android/settings/secrets/actions.
4. Re-run the failed Android job. Successful CI should verify the APK signature and application ID and upload `YoruGram-test-APK`. Do not distribute the debug APK as a production release. CI currently generates a fresh test signing key per run, so subsequent APKs may require uninstalling the earlier test build.

## Windows x64 companion client (planned)

The Android Gradle project cannot produce a native Windows EXE. Use a separate fork, `YoruGram-Desktop`, of https://github.com/telegramdesktop/tdesktop. Reviewed upstream dev revision: `3fad5a7ff199a846922293cecd7d1e63c052adab` (7.4.6). See its [Windows build instructions](https://github.com/telegramdesktop/tdesktop/blob/3fad5a7ff199a846922293cecd7d1e63c052adab/docs/building-win.md).

- Visual Studio 2026, MSVC 14.44, Windows SDK 10.0.26100.0, Python, recursive submodules, upstream dependency preparation.
- Integrate independent YoruGram branding and resources, separate app identity and data directory, retain GPL notices. Disable the upstream automatic updater until a verified independent update mechanism exists.
- Use the project's own Telegram API credentials via protected build configuration, never commit credentials.
- Implement and test YoruGram settings, wallpapers, and supported proxy options in the native desktop client.
- Build Windows x64 using the upstream CMake procedure. Verify the resulting executable and its dependencies, test login with an authorized test account and coexistence with the official client, then package as a ZIP with SHA-256.
- A separate fork and Windows runner are required. No Windows source modifications, EXE build, or runtime tests have been completed.

