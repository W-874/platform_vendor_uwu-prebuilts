#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import tomllib
from zipfile import BadZipFile, ZIP_STORED, ZipFile


FEATURE = b"org.uwuaosp.feature.MIPUSH\0"
ABIS = {"arm64-v8a", "armeabi-v7a", "x86", "x86_64"}
NATIVE_LIB = re.compile(r"lib/([^/]+)/([^/]+\.so)")
JAR_SIGNATURE = re.compile(r"META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC)|SIG-[^/]+)", re.I)


def command(*args):
    return subprocess.check_output(args, text=True)


def stage(root, tools, temp, key, cert, fingerprint, project, flavor, package, filename, version=None):
    outputs = root / project / "build/outputs/apk" / flavor / "release"
    metadata = json.loads((outputs / "output-metadata.json").read_text(encoding="utf-8"))
    if metadata["variantName"] != f"{flavor}Release" or metadata["applicationId"] != package:
        raise ValueError(f"{outputs}: unexpected Gradle variant or application ID")
    candidates = [element for element in metadata["elements"] if not element["filters"]]
    if len(candidates) != 1:
        raise ValueError(f"{outputs}: expected one universal release APK")
    element = candidates[0]
    output_apk = element["outputFile"]
    if Path(output_apk).name != output_apk or not output_apk.endswith(".apk"):
        raise ValueError(f"{outputs}: invalid APK filename")

    source = outputs / output_apk
    badging = command(tools / "aapt2", "dump", "badging", source)
    expected_version = version if version is not None else element["versionCode"]
    match = re.search(r"^package: name='([^']+)' versionCode='([0-9]+)'", badging, re.M)
    if (not match or expected_version <= 0 or element["versionCode"] != expected_version
            or match.groups() != (package, str(expected_version))):
        raise ValueError(f"{filename}: expected {package} versionCode {expected_version}")
    if "application-debuggable" in badging or re.search(r"^package: .*\bsplit=", badging, re.M):
        raise ValueError(f"{filename}: expected a non-debuggable standalone APK")
    # Reject stock/upstream artifacts even when their package and version match.
    unsigned = temp / "unsigned.apk"
    aligned = temp / "aligned.apk"
    staged = temp / filename
    with ZipFile(source) as apk:
        native_libs = {}
        for name in apk.namelist():
            if match := NATIVE_LIB.fullmatch(name):
                abi, library = match.groups()
                native_libs.setdefault(library, set()).add(abi)
        for library, abis in native_libs.items():
            if missing := ABIS - abis:
                raise ValueError(f"{filename}: {library} missing ABIs: {', '.join(sorted(missing))}")
        if not any(FEATURE in apk.read(name) for name in apk.namelist()
                   if re.fullmatch(r"classes[0-9]*\.dex", name)):
            raise ValueError(f"{filename}: missing the uwuAOSP feature contract")
        # Soong's preprocessed import requires stored JNI. The final signing
        # must happen after rewriting the APK and aligning those entries.
        with ZipFile(unsigned, "w") as prepared:
            for entry in apk.infolist():
                if not JAR_SIGNATURE.fullmatch(entry.filename):
                    data = apk.read(entry)
                    if NATIVE_LIB.fullmatch(entry.filename):
                        entry.compress_type = ZIP_STORED
                    prepared.writestr(entry, data)

    subprocess.run([tools / "zipalign", "-P", "16", "-f", "4", unsigned, aligned], check=True)
    subprocess.run([
        tools / "apksigner", "sign", "--key", key, "--cert", cert,
        "--v4-signing-enabled", "false", "--out", staged, aligned,
    ], check=True)
    signing = command(tools / "apksigner", "verify", "--print-certs", staged)
    fingerprints = re.findall(r"^.+certificate SHA-256 digest: ([a-fA-F0-9]{64})$", signing, re.M)
    if {digest.lower() for digest in fingerprints} != {fingerprint}:
        raise ValueError(f"{filename}: APK does not have the dedicated MiPush signer")
    subprocess.run([tools / "zipalign", "-c", "-P", "16", "4", staged], check=True)

    return staged


def main():
    parser = argparse.ArgumentParser(description="Publish universal MiPush prebuilts for uwuAOSP.")
    parser.add_argument("mipush_framework", type=Path, help="patched checkout with fresh Gradle release outputs")
    parser.add_argument("build_tools", type=Path, help="Android SDK build-tools directory")
    parser.add_argument("signing_key", type=Path, help="private DER PKCS#8 key matching mipush.x509.pem")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parent
    root = args.mipush_framework.resolve()
    tools = args.build_tools.resolve()
    cert = destination / "mipush.x509.pem"
    key = args.signing_key.resolve()
    try:
        fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))).hexdigest()
        with (root / "gradle/libs.versions.toml").open("rb") as catalog:
            version = int(tomllib.load(catalog)["versions"]["pushVersionCode"])
        with tempfile.TemporaryDirectory(dir=destination) as directory:
            temp = Path(directory)
            xmsf = stage(root, tools, temp, key, cert, fingerprint, "xmsf", "normal", "com.xiaomi.xmsf", "MiPushXmsf.apk", version)
            manager = stage(root, tools, temp, key, cert, fingerprint, "mipush", "github", "io.github.magisk317.mipush", "MiPushManager.apk")
            for apk in (xmsf, manager):
                apk.replace(destination / apk.name)
                print(f"Staged {apk.name}")
    except (OSError, ValueError, KeyError, BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\nBuild :xmsf:assembleNormalRelease and :mipush:assembleGithubRelease from the patched checkout.\n")


if __name__ == "__main__":
    main()
