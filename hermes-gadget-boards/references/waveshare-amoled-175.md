# Waveshare ESP32-S3-Touch-AMOLED-1.75 — gadget port

SKU 31261 (B = with case, G = GPS variant). Gadget board option: `esp32s3-touch-amoled-175`.

## Silicon / parts map

| Part | Chip | Connection |
|---|---|---|
| SoC | ESP32-S3R8 | 8 MB octal PSRAM, 16 MB flash, BOOT = GPIO 0 |
| Display | CO5300, QSPI | CS 12, SCLK 38, D0–D3 4/5/6/7, RST 39; column offset 6 |
| Touch | CST9217 | I2C 0x5A, RST 40 (INT 11 unused: polled) |
| Speaker DAC | ES8311 | I2C 0x18; I2S MCLK 42, BCLK 9, WS 45, DOUT 8; amp enable 46 |
| Microphones | ES7210 (dual array) | I2C 0x40; I2S DIN 10 (shares bus above) |
| Power | AXP2101 PMIC | I2C 0x34, left at power-on defaults; battery charger onboard |
| I/O expander | TCA9554 | I2C 0x20; P4 mirrors the PWR key |
| I2C bus | | SDA 15, SCL 14, 400 kHz |

Also onboard: 6-axis IMU, RTC, 466x466 1.75" round AMOLED. NO onboard speaker — plug a small 8-ohm speaker into the SPK connector for replies.

## Controls (touch-first, unlike the M5Stick's button)

| Gesture | Action |
|---|---|
| Hold screen | TALK; lift to send |
| Tap | answer "yes" |
| Swipe down | CANCEL / "no" / close card / stop turn |
| PWR key | CANCEL; hold 2 s = new conversation |
| Hold BOOT | TALK (fallback) |
| Lay face down | sleep (off by default) |

Remap via `set touch_cancel swipe|pwr|both` (both = default). Same gestures work on the `sim-466x466-round` simulator board with a mouse.

## Build

```bash
cd firmware/esp32
pio run -e esp32s3-touch-amoled-175 -t upload -t monitor
```

## First-flash verification checklist

1. Boot log: `CO5300 466x466 ready`, `codecs: speaker ready, microphones ready`, `touch ready, key ready`. A `did not answer`/`missing` line names the part to inspect. `hg.diag` lines summarize: reset reason, memory, `parts: display co5300, microphone es7210, speaker es8311, touch yes, key yes`.
2. `hermes-gadget diag --port COMx` (or `console --port COMx`, answers `status`): I2C scan must include 0x18 (ES8311), 0x20 (TCA9554), 0x34 (AXP2101), 0x40 (ES7210), 0x5A (CST9217).
3. Screen: mascot centred, upright, not mirrored; amber accents (blue = orientation/mirror wrong); edge stripe = column offset wrong.
4. Touch: hold -> listening waves appear; swipe DOWN (not up) cancels — reversed = flip touch mirroring.
5. Anything wrong: send the `diag` report upstream (port was written from Waveshare's published pinout, so first physical reports are what make the port trustworthy).

## Field-verified bring-up (SKU 31261, fw 0.4.1 source build, 2026-10-30)

Flash via PlatformIO succeeded (4x 'Hash of data verified'), boot good: IDF console answers `status` JSON on the USB-C port (`board: esp32s3-touch-amoled-1.75`, `phase: no_network`, `screen: setup`). The setup SoftAP is HIDDEN — `nmcli dev wifi list` never shows it; don't conclude the AP is dead from a scan. Provisioning over the serial console beats the AP: `wifi add "SSID" "pass"`, `set server ws://<host>:8765/gadget`, then watch `status` go connected -> pairing code -> approve. If phase sits at `connecting` and the gateway log shows NO connection attempts: ufw on this host silently drops inbound 8765 — fix once: `sudo ufw allow proto tcp from <your-LAN-subnet> to any port 8765`. Read the code from `status`'s `pairing_code` and approve non-interactively: `hermes pairing approve gadget <CODE>`. First paired device becomes the gadget platform's home channel.

Serial access without re-login: `sg` does not exist on Arch, and `systemd-run -p SupplementaryGroups=` fails 216/GROUP. Working recipe (after `sudo usermod -aG uucp`):

```bash
newgrp uucp <<'EOF'
export HOME=/home/<your-username>   # newgrp shell may inherit wrong HOME; force it
~/.local/share/uv/tools/platformio/bin/python -c "import serial; ..."
EOF
```

pyserial is in the uv platformio tool venv; `python -m esptool` is NOT (pio runs esptool via its own loader). Hand-rolled DTR/RTS pulses can park the chip in download mode — just replug USB-C and poll for the port.

NEVER `sudo pio run -t upload` even with HOME= set: it re-ran CMake as root, wrote ~2000 root-owned files into .pio/build and poisoned CMakeCache with /root/.platformio paths; repair = `sudo chown -R <user> <project>` + `rm -rf .pio/build/<env>` + rebuild.
