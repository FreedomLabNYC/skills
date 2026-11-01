# Interactive Device Viewer

Build, test, and publish interactive Three.js exploded-assembly device pages — taught via the live FreedomLab voice-hardware page at [freedomlab.nyc/voicehardware](https://freedomlab.nyc/voicehardware/), where every device model is built from source-grounded measurements.

This skill teaches an AI agent the proven workflow for:

- Adding a new 3D device study to `hardware-models.js`
- Editing the minified single-line `index.html` safely (marker-slice + assert, never blind regex)
- Reordering/renumbering devices without breaking QA or SEO copy
- Running the Playwright QA suite (`verify_site.py`) at 1440 + 390 viewports
- Publishing from the source repo to the live site through the website repo (build → audit → cache-buster poll → live proof)

**Source repo:** [FreedomLabNYC/voicehardware](https://github.com/FreedomLabNYC/voicehardware) — the QA and build scripts referenced by this skill live there under `scripts/`.

## What's Included

- `SKILL.md` — Full skill instructions for AI agents

## Installing

Point your agent (Hermes, Claude Code, or any SKILL.md-aware agent) at this directory, or read `SKILL.md` directly.
