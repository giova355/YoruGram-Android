# YoruGram 0.1.0 Foundation

Unofficial Telegram Android fork. The upstream GPL license and notices remain in place.

This branch integrates the independent YoruGram settings screen, localized wallpaper gallery, PNG export and a shortcut to the built-in Telegram proxy configuration. The included WebP resources are reduced-resolution versions of the Foundation artwork. Chat wallpaper application is still manual after export. Managed proxy servers, trial access, billing and owner entitlements are not implemented.

## Test build

Android SDK 36, NDK 27.2.12479018, CMake 3.22.1, Java 17 and recursive git submodules are required. Use your own Telegram API ID and hash from https://my.telegram.org, and your own Firebase project. Its google-services.json must include org.yorugram.messenger.web and the library namespace org.telegram.messenger. Set the environment variables YORU_API_ID, YORU_API_HASH and YORU_FIREBASE_JSON; run python3 yoru-build/configure.py in the repository root, replace the dummy release keystore with your own test key and configure signing properties before running:

```sh
bash gradlew --no-daemon :TMessagesProj_AppStandalone:assembleAfatDebug
```

Do not commit API credentials, Firebase files, signing keys or passwords. This is a private testing build only; the upstream debug configuration exposes diagnostic features. Production builds require a stable signing key and review of other upstream service credentials, package dependencies, branding, and licenses. Android build and runtime are not yet verified.
