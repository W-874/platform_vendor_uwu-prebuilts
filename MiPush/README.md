# MiPush prebuilts for uwuAOSP

All uwu products include `com.xiaomi.xmsf` and `io.github.magisk317.mipush`
under `/product/app` and advertise `org.uwuaosp.feature.MIPUSH`. Normal ROM
builds consume the checked-in APKs as-is: no Gradle build, staging command, or
private signing key is required.

## Updating the prebuilts

Build the patched `MiPushFramework` checkout. Use the normal XMSF and original
(`githubRelease`) manager variants. Configure the upstream SDK/JDK and release
signing as usual; the Gradle key is not the installed signer. Do not substitute
stock APKs or packages downloaded from an upstream release. From the workspace
containing `MiPushFramework` and `uwuAOSP-src`:

```sh
(cd MiPushFramework && ./gradlew :xmsf:assembleNormalRelease :mipush:assembleGithubRelease)
cd uwuAOSP-src
python3 vendor/uwu-prebuilts/MiPush/stage-apks.py ../MiPushFramework \
    "$ANDROID_HOME/build-tools/37.0.0" /secure/path/mipush.pk8
```

The script requires Python 3.11+. It checks the Gradle output metadata, package
IDs, version codes, compiled uwuAOSP feature marker, and native libraries for
ARM and x86 (32-bit and 64-bit). It stores and aligns native libraries before
signing and verifies both APKs against the public `mipush.x509.pem` certificate.
Keep the matching private DER PKCS#8 key outside the source tree. Include both
updated APKs in the same change.

The initial pair uses a dedicated development signer, not the platform or
ROM default key. For a production release, provision a dedicated production
key with restricted access and use its certificate and APKs together. Keep
that production signer stable across updates: an unrelated certificate cannot
replace these packages as a normal signed update.

## OTA and device smoke check

From `uwuAOSP-src`, source `build/envsetup.sh`, lunch the appropriate uwu target
(e.g. `lunch uwu_sagit-cp2a-userdebug`), and build with `m otapackage`. Install
the resulting OTA using the device's supported update procedure (e.g. recovery
ADB sideload for Sagit) and reboot.

1. With non-root ADB, run `adb shell pm has-feature org.uwuaosp.feature.MIPUSH`.
   Both packages should resolve under `/product/app` with `adb shell pm path PACKAGE`.
   Pull both APKs with `adb pull` and run `apksigner verify --print-certs` on each.
   Both certificate SHA-256 digests must match `openssl x509 -in
   vendor/uwu-prebuilts/MiPush/mipush.x509.pem -noout -fingerprint -sha256`.
2. In the Android user being tested, use a freshly installed third-party MiPush
   client with no notification delegate. Enable its notifications and complete
   registration with its valid app ID/key. Do not run `allow_mipush`. After the
   server confirms registration, check the client's `AppSettings` in `adb shell
   dumpsys notification`: its enabled delegate should be `com.xiaomi.xmsf`.
3. Send, update, and cancel a notification through MiPush. In
   `adb shell dumpsys notification`, check that `pkg`, UID, and channel belong
   to the client while `opPkg` is `com.xiaomi.xmsf`. Find the client's UID with
   `adb shell cmd package list packages -U --user current PACKAGE`.
4. Run `adb shell cmd notification disallow_mipush PACKAGE`. Register again
   without uninstalling: the delegate must stay disabled, and a new push must
   not post for the app. Use `adb shell cmd notification allow_mipush PACKAGE`
   to restore delegation explicitly. Test a progress notification with and
   without the client's native promotion eligibility.
   Confirm a promoted notification when eligible and an ordinary notification
   otherwise, both attributed to the client.
