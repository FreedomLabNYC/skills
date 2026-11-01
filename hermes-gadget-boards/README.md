# Hermes Gadget Boards

Flash and pair ESP32-S3 Hermes Gadget boards — hold-to-talk voice endpoints for a local Hermes gateway. Covers the browser-installer and PlatformIO source-build paths, OTA updates, and the failure modes that eat whole afternoons: stale espressif32 platforms, serial-group permissions on Arch, hidden setup SoftAPs, silent-firewall pairing stalls, and "audio broken" reports that are just a missing speaker.

Includes field-verified bring-up data for the Waveshare ESP32-S3-Touch-AMOLED-1.75 (SKU 31261): full chip/pin map, touch gesture table, I2C scan checklist.

**SDK:** [github.com/Adolanium/hermes-gadget-sdk](https://github.com/Adolanium/hermes-gadget-sdk) (MIT)

## What's Included

- `SKILL.md` — Full skill instructions for AI agents
- `references/waveshare-amoled-175.md` — board-specific silicon map + first-flash verification checklist
