---
name: hermes-gadget-boards
description: Use when flashing or pairing a Hermes Gadget ESP32 board.
version: 0.1.0
author: Freedom Lab NYC
license: MIT
metadata:
  hermes:
    tags: [esp32, hardware, hermes-gadget, waveshare]
    related_skills: [hermes-agent]
---

# Hermes Gadget board setup

## When to Use

Unboxing, flashing, pairing, or programming any Hermes Gadget board (Waveshare ESP32-S3 LCD/AMOLED variants, ESP-VoCat, AIPI, Raspberry Pi clients); triaging 'screen colors wrong' / 'no audio' / 'touch reversed' reports on one; or deciding whether a board is supported before promising a build.

Hermes Gadget (github.com/Adolanium/hermes-gadget-sdk, MIT, community-tier) turns ESP32-S3 boards with screen+mic into hold-to-talk chat endpoints for the local Hermes gateway. The SDK may be cloned at `~/Projects/hermes-gadget-sdk`; if not, read docs straight from raw GitHub: `https://raw.githubusercontent.com/Adolanium/hermes-gadget-sdk/main/docs/<file>.md` (supported-hardware.md, hardware.md, setup-board.md, connect-hermes.md, hardware-validation.md).

## Prerequisites (check before touching hardware)

1. Gadget plugin installed — it is not bundled; catalog entry lives at `~/.hermes/hermes-agent/plugin-catalog/gadget.yaml` (needs Hermes >=0.21.6). Check `~/.hermes/plugins` first; on a fresh setup it is absent.
2. STT + TTS configured in Hermes for voice (the plugin reuses Hermes's own); without them the device still displays replies and takes text via the USB console.
3. Gateway listens on ws port 8765, all interfaces, plain ws, serving WebSocket ONLY at path `/gadget` (LAN/private-first is fine). The canonical device address is the `device URL` line of `hermes gadget info` (e.g. `ws://<host-ip>:8765/gadget`) — a hand-typed bare `host:port` or missing `ws://` scheme fails the same as no server. Plain HTTP on that port, or a ws connect to root `/`, returns a deliberate `404 Not a Hermes gadget endpoint` (hub.py `_check_request`): that response PROVES the listener is healthy, it is not a fault, and it is also the signature seen when another tool's address field expects the HTTP dashboard (:9119) but was given the gadget port. New devices need a Hermes pairing code unless listed in `GADGET_ALLOWED_USERS`; `GADGET_ALLOW_ALL_USERS` is dev-only.
4. First approved device becomes the platform's home channel — confirm that's intended before pairing.

## Identify the exact board first

The user often only knows "the Waveshare thing I ordered"; the copied product page is the ground truth. Grep the clipboard history: `grep -o 'https://[^"]*waveshare[^"]*' ~/.local/state/omarchy/clipboard-history.json | sort -u` — the SKU in the query string pins the exact revision (e.g. 31261 = ESP32-S3-Touch-AMOLED-1.75). Then match it to a supported board in docs/supported-hardware.md; supported boards have a PlatformIO env name (e.g. `esp32s3-touch-amoled-175`). Never hand-write firmware against a guessed pinout when an official profile exists, and check docs/hardware-validation.md before calling a port "verified" — hardware ports stay experimental until a physical verification report is recorded for the exact revision.

## Flash paths

- No toolchain (preferred first flash): browser installer https://adolanium.github.io/hermes-gadget-sdk/installer.html — Chrome/Edge + USB data cable + 2.4 GHz Wi-Fi; Wi-Fi can also be configured later from a phone via the gadget's temp AP.
- Source build: `git clone` the SDK, then `cd firmware/esp32 && pio run -e <board-env> -t upload -t monitor`. Profiles merged after the latest release exist only in source builds — releases carry prebuilt firmware for their listed profiles.
- After first flash, upgrades go OTA: `hermes gadget update --latest` (SHA-256 checked against the release manifest; a build that can't reach Hermes rolls itself back).

## Pitfalls

- Stale espressif32 platform silently breaks new builds: `platform = espressif32` unpinned KEEPS whatever version already sits in `~/.platformio/platforms/` (never auto-upgrades). The SDK needs ESP-IDF >=6.0 symbols (e.g. CONFIG_MBEDTLS_CERTIFICATE_BUNDLE_CROSS_SIGNED_VERIFY) → espressif32 >=8.0.0 (bundles IDF 6.1); old 6.12.0 resolves IDF 5.5 and the repo's own sdkconfig-vs-defaults check fails with 'the config has nothing'. Fix: `pio platform update espressif32`. CI looks green because clean runners always resolve latest.
- Serial access on Omarchy/Arch: `/dev/ttyACM*` is root:`uucp` 660; the user is often in NO serial group → upload dies with Errno 13. Permanent fix (needs user's sudo): `sudo usermod -aG uucp <your-username>`. No re-login required — after usermod, run serial work inside `newgrp uucp <<'EOF' ... EOF` with an explicit `export HOME=/home/<your-username>` inside the heredoc (Arch ships no `sg`; `systemd-run -p SupplementaryGroups=` fails 216/GROUP; newgrp may inherit a wrong HOME). NEVER `sudo pio run -t upload` even with HOME set: it re-runs CMake as root, leaves thousands of root-owned files in the build tree and poisons CMakeCache with /root/.platformio paths — repair is `sudo chown -R <user> <project>` + `rm -rf .pio/build/<env>` + rebuild.
- ESP32-S3 USB-C ports are the SoC's native USB: shows up as "USB JTAG/serial debug unit", and both flashing and the serial console (`hermes-gadget console --port COMx`) use it — no separate UART bridge needed. If the console log prints but commands go unanswered, console is still on UART0.
- Boards with a speaker DAC but no onboard speaker (e.g. AMOLED-1.75) are silent until an 8-ohm speaker is plugged into the SPK connector — "audio broken" reports are often a missing speaker.
- Round AMOLED panels have a column offset; a thin stripe at one screen edge means the offset is wrong, and amber-vs-blue accent color reveals an upside-down/mirrored panel, not a driver bug.
- The ws listener binds only at gateway PROCESS start: after `hermes config set platforms.gadget.enabled true` a plugin disable/enable hot-reload makes hooks live and `hermes gadget info` reports `platform enabled: True`, but 8765 stays unbound (`ss -tln | grep 8765` empty) until the gateway restarts. Hermes blocks restarting the gateway from inside a gateway-hosted agent session — check first with `ps -o ppid=,comm=` walking up from your own shell (desktop/CLI sessions commonly parent to the gateway PID) — so have the user run `systemctl --user restart hermes-gateway` in their own terminal; the desktop app reconnects and the session survives.
- Verifying a flash WITHOUT serial access: the setup SoftAP of a fresh board is HIDDEN — `nmcli dev wifi list` never shows it, so scan absence proves nothing. Verify via the serial console `status` JSON (needs group access), read the esptool tail (`Hash of data verified` + hard reset = write succeeded), and ask the user what the screen shows. Don't treat USB re-enumeration as proof either way: native-USB S3 can flash and hard-reset WITHOUT recreating the /dev/serial/by-id symlink.

## Board-specific depth

- `references/waveshare-amoled-175.md` — full chip/pin map, touch gesture table, and the first-flash verification checklist for the ESP32-S3-Touch-AMOLED-1.75.
