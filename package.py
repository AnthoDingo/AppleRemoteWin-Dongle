# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AnthoDingo
#
# Packs the signed PlatformIO builds into dist/ for a release (run after `pio run -e xiao_esp32s3 -e xiao_esp32s3_debug`):
#   AppleRemoteEsp32.bin, AppleRemoteEsp32-debug.bin
#       signed app images, sent by the Windows app over USB (its only update channel)
#   AppleRemoteEsp32-factory.bin, AppleRemoteEsp32-debug-factory.bin
#       whole flash (bootloader, partition table, OTA data, app) for the first flash by cable:
#       esptool.py --chip esp32s3 write_flash 0x0 AppleRemoteEsp32-factory.bin
#   SHA256SUMS.txt
#
# Usage: python package.py <version>   (version as in CONFIG_APP_PROJECT_VER, e.g. 1.2.0)

import hashlib
import os
import subprocess
import sys

ENVS = {"xiao_esp32s3": "AppleRemoteEsp32", "xiao_esp32s3_debug": "AppleRemoteEsp32-debug"}
SECTOR = 4096
APP_DESC_VERSION = 48   # esp_app_desc_t.version, after the image header (24) and the first segment header (8)


def is_signed(image):
    """Secure Boot V2 signature sector at the end, on a 4 KB boundary (same check as sign.py and the app's FirmwareImage)."""
    return len(image) % SECTOR == 0 and image[-SECTOR:-SECTOR + 2] == b"\xE7\x02"


def main(version):
    esptool = os.path.join(os.path.expanduser("~"), ".platformio", "packages", "tool-esptoolpy", "esptool.py")
    os.makedirs("dist", exist_ok=True)
    for env, name in ENVS.items():
        build = os.path.join(".pio", "build", env)
        with open(os.path.join(build, "firmware.bin"), "rb") as f:
            app = f.read()
        if not is_signed(app):
            sys.exit(f"{env}: firmware.bin is not signed")
        stamped = app[APP_DESC_VERSION:APP_DESC_VERSION + 32].split(b"\0")[0].decode()
        if stamped != version:
            sys.exit(f"{env}: the image says {stamped}, the release is {version}")
        with open(os.path.join("dist", name + ".bin"), "wb") as f:
            f.write(app)
        # Offsets: partitions.csv and the build's flash_args
        subprocess.check_call([
            sys.executable, esptool, "--chip", "esp32s3", "merge_bin",
            "-o", os.path.join("dist", name + "-factory.bin"),
            "--flash_mode", "dio", "--flash_freq", "80m", "--flash_size", "4MB",
            "0x0", os.path.join(build, "bootloader.bin"),
            "0x8000", os.path.join(build, "partitions.bin"),
            "0xd000", os.path.join(build, "ota_data_initial.bin"),
            "0x10000", os.path.join(build, "firmware.bin"),
        ])
    with open(os.path.join("dist", "SHA256SUMS.txt"), "w", newline="\n") as sums:
        for name in sorted(os.listdir("dist")):
            if name != "SHA256SUMS.txt":
                with open(os.path.join("dist", name), "rb") as f:
                    sums.write(f"{hashlib.sha256(f.read()).hexdigest()}  {name}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python package.py <version>")
    main(sys.argv[1])
