---
name: mediamtx-livestream-hub
description: Use when running a self-hosted RTMP/HLS stream hub.
---

# MediaMTX livestream hub (ingest -> HLS -> fanout -> announce)

Class: OBS pushes one RTMP stream to a VPS MediaMTX; viewers get HLS; platforms get restream copies; nostr gets a NIP-72 announcement. Design rule: frontends (zap.stream etc.) are disposable — the stream must live on your own infra.

## Procedure
1. Ingest check end-to-end before touching config: push a synthetic stream (`ffmpeg -re -f lavfi -i testsrc ... -c:v libx264 -g 60 -f flv rtmp://<vps>:<port>/live/<key>`) and pull the HLS master playlist over HTTPS. A 200 master m3u8 with a variant line = healthy; expect a 302 ?session= cookie dance behind MediaMTX >=1.18 — do not panic-test with plain curl.
2. Config lives host-side (e.g. /root/mediamtx/mediamtx.yml) mounted :ro into the container. Edit, then `docker restart mediamtx`. ALWAYS validate enum values against the running version's error log — invalid values crash-loop the container (see pitfalls).
3. Recording: `record: yes` + `recordPath:` with `%path/%Y-%m-%d_%H-%M-%S`; mount a host dir for the record path (the default container has none) and confirm a file lands after a short test push. Budget disk at bitrate x time (~450 MB/h @ 1 Mbps).
4. Fanout to X/YouTube/Twitch: `publishers:` list under the path (pure stream-copy, no re-encode — fine on a 1 GB VPS). Needs each platform's RTMP URL+key first.
5. Announce layer: keep one signer used by BOTH CLI script and any web UI (UI calls a local sidecar that shells to the same script) so identity never forks. Test publish->read-back per relay; treat per-relay failures as non-fatal.

## Pitfalls
- hlsVariant valid values are lowercase (`mpegts`, `fMP4` variants per docs of the pinned version); writing `lowlatency`/`mp4`/`fMP4`-as-guessed crash-loops the container with only "invalid HLS variant" in logs. After ANY config edit, watch `docker ps` status for a full restart cycle (>30 s) before declaring success — the restart backoff makes a quick poll lie.
- Rebuilding a long-running container (new mounts) requires stop+rm+run with the ORIGINAL flags (--network host, --restart unless-stopped); snapshot the prior `docker inspect` mounts first or you lose the config mount layout.
- The control-server pattern (serve UI + proxy VPS API over SSH): set `allow_reuse_address` before binding, and put the systemd user unit in place early — killing the manual background process while the service also runs causes port fights that look like "server won't start".
- OBS stays the encoder/source-of-truth for scenes; the hub never re-encodes. Stream key choice determines the HLS path name (`/live/<key>/index.m3u8`) — pick the key to match the URL you'll advertise, don't rename later.
