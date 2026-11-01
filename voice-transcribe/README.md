# Voice Transcribe

Local speech-to-text with faster-whisper — no cloud, no API keys, no data leaving the machine. Handles voice messages from Telegram/WhatsApp/Discord and any ogg/opus/mp3/wav/m4a/flac file, with optional local Ollama analysis: summaries, action items, key points, and speech-error enhancement.

CPU-only by default (int8 quantized) with a model-size guide from `tiny` (~32x realtime) to `large-v3`.

## What's Included

- `SKILL.md` — Full skill instructions for AI agents
- `scripts/transcribe_voice.py` — transcription (text/json/srt, per-segment timestamps, auto language detect)
- `scripts/transcribe_with_analysis.py` — transcription + Ollama analysis (`--analyze`, `--enhance`)
