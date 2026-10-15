# AppleRemoteWin-Dongle

ESP32-S3 firmware (ESP-IDF, NimBLE + TinyUSB): a USB dongle that keeps the Siri Remote gen 1 by itself, for
[AppleRemoteWin](https://github.com/AnthoDingo/AppleRemoteWin). No WinUSB adapter, no kernel filter: the Windows app
reads it as a plain HID device and drives it.

- BLE central: "Just Works" pairing (legacy, like the app's `Smp.cs`), bond kept in NVS, reconnection after sleep,
  subscription to `0xFC` and unlock (`0xAF` -> `0xF0`) on every connection.
- USB device: one vendor HID collection, VID `0x303A` (Espressif), usage page `0xFF52`.
- Firmware update **only from the Windows app, over USB**, signed images only (see below). The dongle never goes
  online: Wi-Fi is never started, and BLE carries no update path.

Target board: Seeed XIAO ESP32S3 (any ESP32-S3 with its native USB and ≥ 4 MB of flash works).

## Case (3D printing)

`hardware/`: OpenSCAD case for the XIAO ESP32S3 (non-Sense, no pin headers), tray + lid, with ready-to-print STL files.
All versions share the geometry and parameters of `xiao-esp32s3-case.scad` (measure your board with calipers and adjust
them there); the other `.scad` files only pick a variant.

| Variant | Lid | Inside | Files |
|---|---|---|---|
| default | snap (press fit) | board + FPC antenna | `xiao-esp32s3-case`, `-tray.stl`, `-lid.stl` |
| slide | slides in L slots | board + FPC antenna | `xiao-esp32s3-case-slide` |
| compact | snap | board only | `xiao-esp32s3-case-compact` |
| compact SMA | snap | board only, RP-SMA bulkhead (external antenna, U.FL pigtail) | `xiao-esp32s3-case-compact-sma` |
| slide compact | slide | board only | `xiao-esp32s3-case-slide-compact` |
| slide compact SMA | slide | board only, RP-SMA bulkhead | `xiao-esp32s3-case-slide-compact-sma` |

Print: PLA or PETG, 0.2 mm layers, no supports. The lid has 1.8 mm holes above BOOT and RESET: press them with a pin
(BOOT while plugging in for a cable flash, see "Build").

## USB protocol

Mirrored in the app: `src/AppleRemote.Windows/EspDongle.cs` and `src/AppleRemote.Core/FirmwareImage.cs` of AppleRemoteWin.

| Report | Direction | Content |
|---|---|---|
| `1` | in | remote report in `hid.dll` format: `0xFC` + 20 bytes (zero-padded) |
| `2` | in | state (`0` idle, `1` pairing scan, `2` waiting for the bonded remote, `3` connected), battery %, last disconnect reason |
| `3` | feature | command: `0` send state, `1` pair (forget + scan), `2` forget (then idle) |
| `4` | feature | firmware update. SET: `1` begin + size (u32 LE), `2` data + offset (u32 LE) + length + ≤ 57 bytes, `3` end, `4` abort. GET: status, bytes written (u32 LE), running version (32 bytes) |

Update status: `0` idle, `1` receiving, `2` verifying, `3` accepted (reboots), `0x81`… refused
(`0x82` size, `0x83` chunk out of order, `0x84` flash write, `0x85` incomplete, `0x86` signature/integrity,
`0x87` older version, `0x88` other project, `0x89` boot partition).

No bond at boot: scans for a remote in pairing mode (Menu + Volume+ ~5 s).

## Build

The signing key must exist before the first build (see "Signing key"): no unsigned updatable firmware is ever produced.
Two toolchains, same sources (`CMakeLists.txt`, `idf_component.yml`, `sdkconfig.defaults`, `partitions.csv`):

**PlatformIO** (VS Code): open this repository's root (where `platformio.ini` is), then Build / Upload.
Environments `xiao_esp32s3` (shipped firmware) and `xiao_esp32s3_debug` (+ USB log port). `sign.py` signs
`.pio/build/<env>/firmware.bin` after the build (PlatformIO does not) and fails the build without the key. Command line:

```
pio run -e xiao_esp32s3
pio run -e xiao_esp32s3 -t upload
```

The first build of an environment sometimes fails in `ldgen` (`libheap.a: No such file`): a PlatformIO race, run it again.

**ESP-IDF** (>= 5.1), signs `build/AppleRemoteEsp32.bin` by itself:

```
idf.py set-target esp32s3
idf.py build flash monitor
```

Flashing by cable: once this firmware runs, the S3's USB port is the dongle (TinyUSB), no longer a serial port. Hold
**BOOT** while plugging it in to enter the ROM download mode, then upload, then press **RESET**.
A release's `-factory.bin` holds the whole flash (bootloader, partition table, OTA data, app):

```
esptool.py --chip esp32s3 write_flash 0x0 AppleRemoteEsp32-factory.bin
```

The version compared on update is `CONFIG_APP_PROJECT_VER` in `sdkconfig.defaults` (read by both toolchains): bump it for
every release, the release workflow refuses a tag that differs.

### Logs

- **Debug build** (PlatformIO env `xiao_esp32s3_debug`; idf.py: `idf.py -B build-debug -DAPPLEREMOTE_USB_LOG=1 build`):
  the dongle adds a USB serial port next to its HID collection (PID `0x8A53`, product "AppleRemote ESP32-S3 (debug)").
  Upload it by cable (BOOT), then PlatformIO Monitor / `pio device monitor -e xiao_esp32s3_debug`. Only what is logged
  once USB is up: boot messages and very early crashes stay on UART0. Same version as the release build, so the app
  does not replace it on its own: go back by flashing `xiao_esp32s3`.
- **Shipped firmware**: no USB serial port, logs on UART0 only (XIAO: D6 = TX, D7 = RX, 115200 baud) through a 3.3 V
  USB-serial adapter.

## Releases

`.github/workflows/build.yml` (push, pull request) compiles both environments, signed with a **throwaway key** generated
for the run: those images are refused by every real dongle, nothing is uploaded.

`.github/workflows/release.yml` (tag `v1.2.0`, or run manually with the tag) checks that the tag matches
`CONFIG_APP_PROJECT_VER`, builds both environments, signs them with the project key, verifies both signatures, removes
the key, then publishes (`package.py`):

| File | Use |
|---|---|
| `AppleRemoteEsp32.bin` | signed app, shipped by the Windows app (downloaded from the latest release when the app is built in Release) |
| `AppleRemoteEsp32-debug.bin` | signed app with the USB log port |
| `AppleRemoteEsp32-factory.bin`, `AppleRemoteEsp32-debug-factory.bin` | whole flash, for the first flash by cable |
| `SHA256SUMS.txt` | SHA-256 of the files above |

One-time setup of the key on GitHub (Settings > Environments):

1. Create the environment **`release`**: required reviewer = you, deployment branches and tags = `v*` tags only.
2. Add the environment secret **`OTA_SIGNING_KEY`** with the content of `ota_signing_key.pem`, for instance:
   ```
   gh secret set OTA_SIGNING_KEY --env release --repo AnthoDingo/AppleRemoteWin-Dongle < ota_signing_key.pem
   ```
The workflow refuses any secret whose public fingerprint is not the project's (below), and only runs the build after
your approval. The Windows app downloads `releases/latest/download/AppleRemoteEsp32.bin` anonymously: this repository
must be **public** for that (like AppleRemoteWin-Driver).

## Firmware update: security model

The firmware travels with the app (the app itself is updated from GitHub); the dongle only receives it over USB.
Any process on the PC can write to a HID device, so **the dongle is the only judge**; the app is just a pipe.

| Threat | Defence |
|---|---|
| Malicious program on the PC flashes its own firmware | Image must be signed (RSA-3072, Secure Boot V2 format) with the key of the **running** firmware: checked by ESP-IDF in `esp_ota_end` (`CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT`). Unsigned or foreign-signed: refused, the dongle keeps its firmware. |
| Downgrade to an older, signed but flawed firmware | `ota.c` refuses a version lower than the running one (`CONFIG_APP_PROJECT_VER`, after the signature check). |
| Another signed app of the same key | `ota.c` compares `project_name`. |
| Corrupted / truncated transfer | Chunks must arrive in order, without gap or overlap; size announced first; SHA-256 of the image checked by ESP-IDF. |
| New firmware that boots but is broken | Rollback (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`): it is kept only once USB **and** BLE came up (`ota_confirm_running`); otherwise the next reset returns to the previous one. |
| Updatable build without these protections | `ota.c` stops the build (`#error`) if signing or rollback is disabled; `sign.py` fails the build without the key. |
| Bundled file damaged or replaced | The app pre-checks it (`FirmwareImage`: ESP32-S3, this project, signed) and logs its SHA-256; a replaced file still has to pass the dongle's signature check. |
| Release signed with the wrong key, or key leaking from CI | The release workflow checks the key's fingerprint, verifies both signatures, deletes the key before packaging; the secret lives in a protected environment, never available to pull requests. |

Not covered: someone with **physical access** can still flash anything through the ROM download mode (BOOT button + USB).
Closing that needs hardware Secure Boot V2 + flash encryption, which burn eFuses **irreversibly**: a separate production decision,
not enabled here. A program on the PC can also abort an update in progress (local denial of service, no compromise).

### Signing key

Generated once (OpenSSL ships with Git for Windows: `C:\Program Files\Git\mingw64\bin\openssl.exe`):

```
openssl genrsa -out ota_signing_key.pem 3072
```

Project key, public fingerprint (SHA-256 of the PEM public key; not secret):

```
4b8547045f39a213e8d81a3e28bb70ff0cbfa1b6bc8d45de1d241506b474046d
```

Check that a key file is the project's one:

```
openssl rsa -in ota_signing_key.pem -pubout | openssl dgst -sha256
```

- At the root of this repository (path set by `CONFIG_SECURE_BOOT_SIGNING_KEY`); `*.pem` is ignored by git. **Never commit it.**
- Keep an offline backup (password manager, encrypted USB key). Lost key: dongles in the field can no longer be
  updated from the app, only reflashed by hand. Leaked key: anyone can build a firmware your dongles accept.
- The public key is not in the source: the dongle trusts the key that signed its own running firmware.
  Key rotation not designed yet (Secure Boot V2 allows several signature blocks per image, to be studied):
  until then, changing keys means reflashing by hand.

## Not done yet

- Standalone keyboard mode (USB HID keyboard/consumer without the app): needs `Decoder`/`Gestures` ported to C.
- GATT handles are fixed (gen 1 database, see `main.c`), no HID service discovery.
- Test PIDs `0x8A52` / `0x8A53`: request a PID from Espressif before distributing.

## License

AGPL-3.0-or-later, like AppleRemoteWin (see `LICENSE`).
