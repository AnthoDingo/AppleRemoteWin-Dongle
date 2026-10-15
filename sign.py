# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AnthoDingo
#
# PlatformIO post-build step: makes sure the app image is signed (Secure Boot V2 format, RSA-3072) with
# ota_signing_key.pem. idf.py signs by itself (CONFIG_SECURE_BOOT_BUILD_SIGNED_BINARIES); PlatformIO may not.
# The dongle trusts the key of its running firmware: an unsigned image would be refused by the app and the dongle,
# and flashed by cable it would make every later update fail. So the build fails instead of producing one.

import os
import subprocess
import sys

Import("env")  # noqa: F821 (PlatformIO/SCons global)

SECTOR = 4096


def is_signed(path):
    """Signature sector at the end, on a 4 KB boundary, starting with a V2 signature block (0xE7, 0x02)."""
    size = os.path.getsize(path)
    if size < 2 * SECTOR or size % SECTOR:
        return False
    with open(path, "rb") as f:
        f.seek(size - SECTOR)
        return f.read(2) == b"\xE7\x02"


def sign(target, source, env):
    image = str(target[0])
    if is_signed(image):
        print("sign.py: app image already signed by the build")
        return 0
    key = os.path.join(env.subst("$PROJECT_DIR"), "ota_signing_key.pem")
    if not os.path.isfile(key):
        sys.stderr.write("sign.py: ota_signing_key.pem missing (README, 'Signing key'): refusing an unsigned firmware\n")
        return 1
    espsecure = os.path.join(env.PioPlatform().get_package_dir("tool-esptoolpy"), "espsecure.py")
    signed = image + ".signed"
    subprocess.check_call([env.subst("$PYTHONEXE"), espsecure, "sign_data", "--version", "2",
                           "--keyfile", key, "--output", signed, image])
    os.replace(signed, image)
    if not is_signed(image):
        sys.stderr.write("sign.py: the signed image has no signature block\n")
        return 1
    print("sign.py: app image signed with ota_signing_key.pem")
    return 0


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign)  # noqa: F821
