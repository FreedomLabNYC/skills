---
name: programmatic-video
description: Create programmatic video using agent-friendly, self-hosted tools. Covers tool selection (Three.js, Remotion, FFmpeg, Motion Canvas), headless browser capture pipelines, camera-based composition with edge-anchoring math, and final assembly. Use when asked to make videos, animate scenes, create intros/outros, render browser-based animations, capture Three.js scenes, or assemble clips. Also use when debugging blank WebGL renders, solving camera framing/composition problems, or choosing between video creation approaches. Fully self-hosted — no cloud rendering services required.
---

# Programmatic Video

Create videos programmatically using code-first, agent-friendly tools.

## Tool Selection

When the request is ambiguous, ask the user which category fits:

| Request type | Tool | Why |
|---|---|---|
| Branded intro/outro with camera moves | Three.js + Puppeteer + FFmpeg | Real camera, perspective geometry, layer control |
| Narrated explainer with text/slides | Remotion + FFmpeg | Template-driven, data-driven composition |
| Technical diagram animation | Motion Canvas + FFmpeg | Code-first timing, voice sync |
| AI-generated footage | Replicate + FFmpeg | Fast visual generation, deterministic assembly |
| Stitch/subtitle/transcode existing clips | FFmpeg only | Universal backbone |

When the request clearly maps to one tool, don't ask — just use it.

## Remotion Best Practices

When working in Remotion projects, also load the official Remotion agent skill at `.agents/skills/remotion-best-practices/` for coding conventions, component patterns, and API usage guidelines.

## Core Pipeline

All video work follows this flow:

1. **Author scenes** — Three.js, Remotion, Motion Canvas, or raw assets
2. **Capture/render frames** — headless browser, Remotion render, or direct export
3. **Encode with FFmpeg** — always the final step for packaging

FFmpeg is non-negotiable as the backbone. Everything flows through it.

## Three.js Camera Pipeline

For camera-based composition (intros, reveals, parallax, 3D scenes). See `references/threejs-capture.md` for the full pipeline.

### Quick start

```bash
# Start dev server
npx vite --port 8891 --strictPort &

# Capture frames + encode
node scripts/capture-frames.mjs --port 8891 --frames 165 --fps 30 --out ./out/video.mp4
```

### Key rules

- **Never use `--disable-gpu`** in headless Chrome — kills WebGL. Use `--use-gl=angle --use-angle=metal` (macOS) or `--use-gl=angle --use-angle=swiftshader` (Linux).
- Use a `window.__READY__` flag set after textures load. Wait for it before capturing.
- Use `--strictPort` with Vite to prevent port-switching.

## Camera Composition

For any shot with edge-anchoring, framing constraints, or "start zoomed in, pull back" reveals. See `references/camera-composition.md` for the math.

### Ask the user

When composition constraints exist, clarify:
- Which edges should be anchored? (e.g. "wrist at bottom")
- How much breathing room? (e.g. "8% top and sides")
- What should be visible at frame 0? (e.g. "just the background, no foreground text")

### Core workflow

1. **Lock the final hero frame first** — composition, edge alignment, readability
2. **Solve positions from FOV math**, not by nudging world coordinates
3. **Verify rendered frames** before sending — check frame 0, midpoint, and final hold
4. **Move the camera, not the world** — keep scene objects fixed

### Foreground layer visibility

To hide a foreground layer at the start of a pullback:
- Place the layer's z-position further from the camera than the start position
- As the camera pulls back past that z, the layer naturally enters frame
- Never try to hide it by starting the camera extremely close — FOV will catch slivers

## Remotion Pipeline

For template-driven, data-driven videos (explainers, social clips, branded content). See `references/remotion-guide.md`.

### Quick start

```bash
cd project && npm run render
```

Best for: JSON-driven content, reusable templates, narration + captions + dynamic layouts.

## FFmpeg Patterns

Common assembly patterns. See `references/ffmpeg-patterns.md`.

```bash
# Frames to video
ffmpeg -y -framerate 30 -i frames/frame-%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 out.mp4

# Add audio to video
ffmpeg -y -i video.mp4 -i narration.mp3 -c:v copy -c:a aac -shortest out.mp4

# Burn subtitles
ffmpeg -y -i video.mp4 -vf "subtitles=subs.srt" -c:a copy out.mp4
```

## Anti-patterns

- Don't fake camera motion by independently drifting layers — causes drift, edge failures, visible fragments
- Don't use AI to redraw branded text/logos — text fidelity matters more than flashy motion
- Don't start in Blender unless true 3D production is necessary
- Don't use GUI editors as the system of record — prefer code-first tools
