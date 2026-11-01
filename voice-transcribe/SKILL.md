---
name: voice-transcribe
description: Transcribe voice messages and audio files using faster-whisper, with optional Ollama analysis. Use when the user sends voice messages, audio files need transcription, or spoken content needs summarization, action item extraction, or translation. Supports ogg, opus, mp3, wav, m4a, flac formats. Triggers on voice messages from Telegram, WhatsApp, Discord, or any audio attachment.
---

# Voice Transcription

Transcribe audio locally with faster-whisper, optionally analyze with Ollama.

## Environment

Create a dedicated venv once, then run every script with its interpreter (or export `WHISPER_ENV` to point elsewhere):

```bash
python3 -m venv ~/.venvs/whisper-env
~/.venvs/whisper-env/bin/pip install faster-whisper requests
export WHISPER_PY=~/.venvs/whisper-env/bin/python
```

- **Device:** CPU by default (`int8` quantized — runs anywhere); CUDA works if the toolkit is installed.
- **Scripts dir:** Resolve paths relative to this skill's directory

## Quick Transcription

```bash
$WHISPER_PY scripts/transcribe_voice.py /path/to/audio.ogg
```

Options: `--model tiny|base|small|medium|large-v3` `--format text|json|srt` `--output file.txt`

Default model is `base` — good balance of speed and accuracy. Use `small` for important content, `tiny` for quick previews.

## Transcription + Analysis

```bash
$WHISPER_PY scripts/transcribe_with_analysis.py /path/to/audio.ogg --analyze
```

Analysis options:
- `--analyze --analysis-type summary` — summarize key points (default)
- `--analyze --analysis-type action_items` — extract tasks/follow-ups
- `--analyze --analysis-type key_points` — bullet point main ideas
- `--enhance` — fix speech-to-text errors via Ollama before analysis
- `--ollama-model qwen3:8b` — specify Ollama model (default: qwen3:8b)

Combine flags: `--enhance --analyze --analysis-type action_items`

## Workflow

1. Receive audio attachment or file path
2. Run `transcribe_voice.py` with appropriate model size
3. If user wants analysis: run `transcribe_with_analysis.py` with `--analyze` or `--enhance`
4. Present results — keep output concise, quote the full text only if short (<200 words)
5. For long transcriptions, summarize and offer the full text on request

## Model Selection Guide

| Model | Speed | Use Case |
|-------|-------|----------|
| tiny | ~32x realtime | Quick previews, short messages |
| base | ~16x realtime | Default — voice messages, general use |
| small | ~6x realtime | Important content, meetings |
| medium | ~2x realtime | High accuracy needs |
| large-v3 | ~1x realtime | Critical transcriptions, multiple languages |

## Notes

- Script auto-detects language (no need to specify)
- All processing is local — no data leaves the machine
- For SRT subtitles: `--format srt`
- JSON output includes timestamps per segment: `--format json`
- Ollama must be running for `--analyze` or `--enhance` (checked automatically)
