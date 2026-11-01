# Nostr App Development

Teach your agent to build static HTML/JS Nostr apps that actually work: raw NIP-01 WebSocket relay reads/writes, relay-by-relay failure handling, NIP-05 self-hosted domain verification, NIP-72 livestream announcements, and publish→read-back testing with zero browser dependencies.

Distilled from real integrations — including the gotchas public docs never mention: `relay.damus.io`'s transient 503 handshake, `nostr.wine`'s `restricted:` writes, redirects silently killing NIP-05 verification, lowercase-hex-only `nostr.json`, and OK-before-queryable timing.

## What's Included

- `SKILL.md` — Full skill instructions for AI agents
- `scripts/nostr_probe.py` — stdlib-only relay probe (author + kinds → events per relay, no Node/browser/API keys)
- `references/caddy-static-serving.md` — serving public HTTPS thumbnails from a Caddy v2 site block behind Cloudflare (NIP-72 `image` tag pattern)
