---
name: interactive-device-viewer
description: Use when building, QA-ing, or publishing an interactive Three.js exploded-assembly device page — adding, renaming, or reordering a 3D device section, building a new study in hardware-models.js, running the Playwright QA suite, or taking a change from the working tree to GitHub and the live freedomlab.nyc page.
license: MIT
metadata:
  hermes:
    tags: [voicehardware, threejs, website, playwright, esp32]
---

# VoiceHardware interactive assembly site

Source repo: `FreedomLabNYC/voicehardware` (the `site/` dir). The live page
`freedomlab.nyc/voicehardware` is served from a separate website repo — editing
`site/` does not touch it until the publish flow below. Repo push and live
publish are separate, explicitly approved actions.

## Publishing to freedomlab.nyc
1. Website repo: clone `FreedomLabNYC/freedomlabnyc-website` (GitHub Pages + Cloudflare front).
2. `diff -rq site/ voicehardware/` between the source repo and the website route dir — publish is a pure copy; typically only `index.html`, `viewer.css`, `js/hardware-models.js` differ. Copy just the differing files into the route dir.
3. Build + audits (python3 directly, no npm): `python3 scripts/build-site.py && python3 scripts/audit-shared-styles.py && python3 scripts/audit-built-site.py _site`. Serve `_site` and sanity-check `/voicehardware/` before pushing.
4. Commit (GitHub noreply author) + `git push origin HEAD`. Pages + Cloudflare propagate in ~40-60 s — poll `curl 'https://freedomlab.nyc/voicehardware/?cb=$RANDOM' | grep <new-cache-buster>` until hit, then verify the canonical URL too.
5. Live proof: browser-check the `data-ready` viewer count and heading text. Videos autoplay-block in automation — require a user activation (one click) before `video.play()`, assert `currentTime` advances; `curl -r 0-65535` each mp4 expects `206 video/mp4`.
6. Cache-buster convention: value is arbitrary (NOT the css md5); md5-of-content is fine and self-consistent.

## Layout
- `site/index.html`: minified single-line HTML. Each viewer device = `<section class="device" id=... data-device=...>`: device-heading (h2 with `<span>NN</span>` + spec subline) > viewer-grid (viewer: stage + transport + scrub input; aside: description, h3 Inspect, .parts, .selection, .limits) > source-row > gesture. Non-viewer entries are `class="tool"`.
- `site/js/hardware-models.js`: `buildModel(kind)` branch per device; `assembly-viewer.js` is generic, keyed off `data-device` — section ORDER is pure HTML, safe to reorder without touching JS.
- `site/viewer.css` loads with cache-buster `?v=<7hex>` — on any CSS change bump it to the first 7 chars of the md5sum of the new CSS.
- QA: `scripts/verify_site.py` runs `verify_interactive.py` (real Chromium, 1440 + 390 viewports, its own ephemeral server).

## Editing the minified HTML
- Edit via a python script: find/slice between unique markers, `assert html.count(anchor)==1` before every replace, then validate the resulting section-id order programmatically. Patch-tool `old_string` anchors are fragile against one-line blobs.
- NEVER put `\uXXXX` escapes inside a raw string (`r'''...'''`) — raw strings don't decode them and literal `\u2033` text ships into the page. Use plain strings, or repair post-write scoped to the new block: `re.sub(r'\\u([0-9a-f]{4})', lambda m: chr(int(m.group(1),16)), block)`.
- Renumbering a device touches ALL of: jump-nav labels, `<span>NN</span>` headings, intro/disclosure sentences, meta/og/twitter 'N source-grounded' descriptions, and the repo README study list — sweep every count token ('Four'/'Five'/...) with asserts.

## Adding a viewer for a device
1. `hardware-models.js`: insert an `}else if(kind==='<id>')` branch BEFORE the generic `}else{`. Use the file's helpers: `part(root,id,label,description,[explodeOffset])`, `solid()`, `disc()`; `size` = widest device dimension in mm. Part id `board` is REQUIRED (QA clicks `[data-part="board"]`; `update()` gives board/audio/display distinct assembly timings). Reuse the `labelTexture` 'INTERFACE STUDY' canvas motif; for round panels use `CircleGeometry` + a custom square canvas texture — the rectangular `labelTexture` clips its text corners inside a circle.
2. `index.html`: convert the tool section to full device markup (copy a sibling section, swap ids/labels/aria).
3. `verify_interactive.py`: update the `data-ready` count wait, the `[data-device]` order assertion, and the kinds loop — QA hardcodes them and fails otherwise.
4. Geometry honesty is the site's brand: exterior numbers quoted from the manufacturer drawing (`docs/PHYSICAL_REVIEW_*.md`), internals labeled 'photo-estimated, not PCB CAD', screen content 'illustrative'. Naming: short 'Brand Device' h2 matching siblings; the long official manufacturer product name goes in the description, not the heading.

## Running QA
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
python scripts/verify_site.py   # expect "passed": true, zero errors/network_errors
```
Regenerated `qa/interactive/*.png` screenshots (including new per-device ones) commit alongside the change. If pip resolved a newer playwright than the cached browsers, launch fails naming a missing build number — rerun `playwright install chromium` to match versions.

## Preview before approval
Serve the working tree with `python3 -m http.server 8000 --bind 127.0.0.1 --directory site` and hand the reviewer the `http://127.0.0.1:8000/` URL. Verify your own visuals in a real browser before presenting: heading text, `data-ready` count, and the exploded state (dispatch `input` on the scrub range).
