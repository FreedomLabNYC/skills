---
name: nostr-app-development
description: Use when building Nostr relay read/write paths in web apps — publishing, feed readers, NIP-05 verification, relay quirks, and livestream (kind 30311) announcements.
license: MIT
---

# Nostr app development (relay read/write, verification)

For static HTML/JS Nostr apps (publish + feed readers) and their test harnesses.

## Transport choice
- Prefer raw WebSocket NIP-01 (`['REQ',id,filters]` / `['EVENT',ev]`) over CDN-bundled nostr-tools for the READ path — same transport as publish code, works offline/when the CDN bundle fails to load. Keep nostr-tools only for signing helpers.
- REQ pattern per relay: send REQ on open, collect `EVENT` messages matching your req id, on `EOSE` send `CLOSE` then close after a short grace (~400 ms); resolve empty on error/timeout. Fan out with Promise.all; per-relay failure must be non-fatal. Dedupe results across relays by event id (a Set of seen ids so re-syncs don't double-render).

## Relay quirks (probe before assuming)
- Some public relays accept reads but gate WRITES behind signup (e.g. nostr.wine returns OK with `restricted:` message). Treat an OK payload's third field as the acceptance flag, not presence of OK.
- damus-class relays can silently never answer OK — always run publishes under a timeout. relay.damus.io's WS handshake can also return HTTP 503 Service Unavailable — that is transient, not "author has no events"; always query at least two other relays before concluding absence.
- Addressable-event `#a` filter values embed the AUTHOR hex (`kind:pubkey:didentifier`). You cannot build the filter from a d-tag alone — either know the author pubkey or pull recent events of the kind and match the tag client-side.

## Verification workflow (Node 22, no browser needed)
- Node >= 22 has global WebSocket — write `.mjs` scripts that publish a signed test event, poll each relay by `ids:[...]` AND by tag filter, and confirm round-trip before touching UI code.
- To test functions written INSIDE an HTML page: extract the inline `<script>` with regex, slice the section you need, and run it via `new Function(code + 'return {fns...}')` with stubbed globals (the app's state arrays, render no-ops). `eval` at module scope does NOT expose inner declarations — use the Function-return trick.
- Syntax-check every edit to a single-file app: extract all inline script blocks, concatenate, `node --check`. Then load the served page in a real browser and assert DOM text (status line, rendered cards) — the file-level check proves syntax only, not wiring.
- Long-running WS scripts hang node if sockets stay open: give every query its own hard timeout and `process.exit()` on completion; run under shell `timeout` too.

## NIP-05 (self-hosted domain identifier)
- Verification contract: client reads `nip05` = "name@domain" from kind-0, GETs `https://domain/.well-known/nostr.json?name=<local>`; the endpoint MUST answer 200 with NO redirect (fetchers ignore redirects), map name -> pubkey in LOWERCASE HEX (npub form is display-only and invalid here), and send `Access-Control-Allow-Origin: *` or JS clients see a fake "not found". Verify with `curl -sI` checking status 200, empty redirect_url, and the ACAO header before telling the user they're verified.
- The server-side file alone yields no checkmark: the same key must sign a kind-0 carrying the matching `nip05` field. Probe author+kind-0 on ≥2 relays first — if absent, publishing the profile is a required step of the task, done from whatever client holds that key (extension/NIP-07), never by asking the user to paste a private key.
- Static-file recipe behind an already-proxied apex: file at /var/www/.well-known/nostr.json + Caddy named matcher `@nostrjson path /.well-known/nostr.json` + `handle` block (root, file_server, header ACAO *) placed BEFORE the blanket reverse_proxy — pattern and Cloudflare origin verification in the caddy-static-file-serving skill. Include the recommended `relays` map (pubkey hex -> [wss urls]) to help clients find your events.
- npub->hex without dependencies: bech32 data-part is 5-bit groups, drop the trailing 6 checksum chars, convertbits 5->8 — NOT 5->4 (that silently yields a truncated 48-hex-char fake key). Reusable implementation: scripts/nostr_probe.py (also a stdlib websocket relay probe by author+kinds, no Node/browser needed).
- New-domain NIP-05 on a second Cloudflare zone: the existing Caddy DNS-01 token is zone-scoped and cannot mint the new zone's cert — point `A @` grey-cloud (unproxied) so Caddy's default HTTP-01 issues with zero new tokens; only orange-cloud if the user creates a fresh zone-scoped DNS token for the `tls` line.
- If the Caddy block lists `domain.com, www.domain.com`, BOTH hostnames must have DNS records — ACME fails the WHOLE multi-SAN cert when one name is missing, so the site serves nothing. Ask the user to add the www record (or drop www from the block).
- A site-wide `redir` fallback placed after the `@nostrjson` handle block works — the explicit handle consumes /.well-known first, so the JSON is never redirected (redirects are fatal to verification). Add `header Cache-Control "no-store"` on that handle and re-verify through the public hostname after any edit, since a fronting CDN can keep serving a stale nostr.json after key rotation.
- Before deploying, confirm which key IS the user's real public identity by probing author+kind-0 and kind-30311 across relays — the key in the panel's keyfile may be a secondary/archive identity; NIP-05 belongs on the key clients actually see (streams, notes, zap target).

## Pitfalls
- Publish-then-read needs a small sleep (~2 s) — relays acknowledge OK before the event is queryable. The converse also holds: an `OK true` reply does NOT guarantee retrievability — probe with `ids:[...]`, `#d`, and author+kinds filters, and if all return nothing across several relays, treat storage/retention as broken independent of your payload (a plain no-extra-tags control publish isolates tag-schema rejection from relay-side issues).
- Decoding custom kinds back into app shapes: validate ALL required structured tags (return null on any missing/NaN score) so junk events from other clients on shared kinds never render.
- NIP-72 livestream events (kind 30311): `d` tag = stable stream id, plus `title` and a `t` tag carrying the playback URL; republishing the same `d` with empty content serves as stop/update. Keep the signing key in a dedicated file (chmod 600), not the app's identity.
- Thumbnail for livestream clients (zapstream etc.): add an `image` tag whose value is a PUBLIC absolute HTTPS URL — LAN-only URLs (e.g. a local studio proxy) are silently ignored by remote clients. Serve it from the streaming VPS behind the existing TLS hostname, not from the panel box; Caddyfile pattern + Cloudflare-origin verification in references/caddy-static-serving.md. On the VPS side, see the caddy-static-file-serving skill for the working Caddyfile pattern.
- Persist live/announce state SERVER-SIDE at publish time: write the accepted `d` + metadata to a JSON file on OK:true, clear on stop, expose a read endpoint. A panel restart or page reload must never lose the ability to revoke. If only the browser holds the `d` (NIP-07/Alby path signs in-page), mirror it to localStorage AND restore UI state from the server on load, with a 're-announce same d' affordance so caches refresh without minting a new stream id.
- Run relay readback probes ONCE per hypothesis. Repeating identical publish→query tests does not change the answer and floods relays with accepted-but-unqueryable noise; when a probe fails twice, report the finding and move to the next step.
- Revoking a listing whose `d` tag is unrecoverable (signed in another browser before persistence existed): scan other relays for the author's kind-30311 events, or brute-force candidate d-timestamps only within an approximate click window. If neither is available, say so plainly — clients age the listing out once ingest stops; do not silently re-run dead probes.
- Vendored Node libs for CLI scripts: copy each dependency package into `<project>/lib/node_modules/...` preserving that layout — flat copies of scoped packages (`@noble/*`) break bare-specifier resolution inside the main app's own imports.
- Cross-origin LAN bridges (panel page on :8765 polling a helper server on another port): echo `Access-Control-Allow-Origin` only for LAN/loopback hosts parsed out of the Origin header. Regex-validate the origin host strictly (`^https?://([^:/]+)(:\d+)?$` then exact host checks) — a loose pattern like `[\w.-]+` matches any domain and silently opens CORS to the internet; test with a deliberately external Origin header before shipping.
