---
name: android-tv-adb-debloater
description: Use when debloating, swapping the launcher, or adding a video wallpaper to an NVIDIA Shield / Android TV box over Wi-Fi ADB.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [android-tv, shield, adb, ffmpeg, launcher]
---

# Android TV / NVIDIA Shield de-ads + launcher + video wallpaper

## When to Use
Box is slow/ad-laden, launcher swap, video wallpaper, or any ADB-side change on a
Shield/Android TV..

All work runs from PC over Wi-Fi ADB (`adb connect <box>:5555`; approve RSA prompt on TV once).

## Debloat (Shield gotcha)
- `pm disable-user --user 0` on `com.nvidia.*` telemetry packages is REVERTED at boot by
  NVIDIA's package manager. Persistent method: `pm uninstall --user 0 <pkg>` (verified across
  reboots). Undo: `adb shell cmd package install-existing --user 0 <pkg>` — save an undo script.
- Google packages (tvlauncher) DO keep disable-user. Never touch: com.nvidia.ota,
  packagemanagerservice, shieldtech.*, nvaudiosvc, avsync, overscancomp, blakepairing,
  irtuner, shield.welcome (keeps OTA + remote/display plumbing).
- HOME swap: `cmd package set-home-activity` writes the preferred DB but `resolve-activity`
  still prints the old launcher (it ignores prefs) and the Home button may resume the old
  task — force-stop it, then disable-user the stock launcher; verify with
  `dumpsys activity activities | grep ResumedActivity` after a KEYCODE_HOME.
- Animations: `settings put global {window,transition}_animation_scale 0` +
  `animator_duration_scale 0` (no UI toggle exists on Android TV).

## Couchy launcher video wallpaper
- Config = one JSON in DataStore; the app's Settings → Save & load exports/imports it
  (schema in app/src/main/java/com/conreo/couchytv/data/Config.kt).
- Video wallpaper ONLY works via the native Settings → Wallpaper → "Pick a video…" SAF
  picker (takePersistableUriPermission). A config-imported file:// URI never composes a
  player (targetSdk 34 app, no storage perms). Don't burn time on the import route.
- TV DocumentsUI ignores `input tap` — D-pad only (`input keyevent KEYCODE_DPAD_DOWN/CENTER`).
  Use the "Large files" chip to surface big media quickly.
- Player errors/stalls log under tag `LiteTV`; a silent gradient = branch never taken
  (check `adb logcat -d | grep LiteTV` + codec init lines).

## tvOS Launcher (com.techgenius.tvoslauncher) custom wallpaper
- App has NO video wallpaper (bitmap-only, verified in source). Aerial-style personal look
  workaround: pull N frames from a rendered video loop (one per home section, each mid-zoom
  so the blur-fill is baked in), load as Custom scenes via Settings → Appearance and scenes
  → custom picker (files under /sdcard/Download/wallpaper/ after granting READ_MEDIA_IMAGES
  + MANAGE_EXTERNAL_STORAGE appop). Uncheck built-in scenes → rotation = own frames only,
  switching on the app's "stay seconds" timer.
- Frame extraction: `ffmpeg -vf "select='eq(n,FRAME)'" -fps_mode passthrough` — plain `-ss`
  returns identical black frames at clip starts of a zoompan render.
- Settings UI is D-pad only (taps ignored except Control Center). File picker sorts by
  STRING order (`14460 < 25260 < 36060 < 3660`) — zero-pad frame names or scene order scrambles.
- Safety posture: auto-updates OFF, Keep Alive OFF, boot-launch OFF, weather/location OFF,
  no ADB pairing granted, no in-app debloater run.
- Home-role swap is reversible: `cmd package set-home-activity <other>/.MainActivity`
  (system role cmd; previous launcher just needs to stay installed).

## Stills → aerial-style loop (ffmpeg)
- Per-slide 1080p30 clip: split image; bg = scale 3840x2160 increase+crop+boxblur=28:3+
  eq brightness -0.08; fg = fit; overlay; zoompan z='2+0.14*on/119' d=120 s=1920x1080;
  0.4s fade in/out; libx264 crf 22 veryfast. Concat with `-c copy` + `-movflags +faststart`.
- 8 parallel ffmpeg workers max (12 OOMs on 24MP jpgs + 4K blurs).
- Validate clips with `ffprobe duration==4.0`, NOT file size — a killed ffmpeg leaves
  >100KB files with no moov atom. `ffmpeg -y` re-renders corrupt paths in place (no rm needed).
- xargs splits on spaces in paths (e.g. "My Photos") — use a Python ThreadPoolExecutor driver
  reading a TSV, or `-d '\n'`.
- Loop runtime: ~0.5s render per 4s clip per worker for stills; 427 stills ≈ 25s of batch
  wall time with warm cache.

## Verify wallpaper playing
Two `screencap -p /sdcard/…` + `pull` ~3s apart, PIL ImageChops.difference over full frames
(motion ⇒ live). NOTE: `adb exec-out screencap` corrupts the PNG — always file-then-pull.
