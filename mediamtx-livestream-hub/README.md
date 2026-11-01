# MediaMTX Livestream Hub

Run your own livestream infrastructure: OBS pushes one RTMP stream to a MediaMTX server on a VPS, viewers get HLS, social platforms get restream copies (no re-encode — fine on a 1 GB box), and Nostr gets a NIP-72 announcement. Frontends are disposable; the stream lives on your own infra.

Encodes the operational traps: config enums that crash-loop the container, the ?session= redirect dance on MediaMTX ≥1.18, mount-preserving container rebuilds, and restart-backoff polls that lie.

## What's Included

- `SKILL.md` — Full skill instructions for AI agents
