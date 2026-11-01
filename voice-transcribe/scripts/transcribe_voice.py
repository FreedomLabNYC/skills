#!/usr/bin/env python3
"""
Voice transcription script using faster-whisper
Part of the voice-transcribe skill
"""

import sys
import argparse
import json
import os
from pathlib import Path

# Add the whisper environment to Python path
WHISPER_ENV = Path(os.environ.get("WHISPER_ENV", str(Path.home() / ".venvs" / "whisper-env")))
WHISPER_PYTHON = WHISPER_ENV / "bin" / "python"

def get_whisper_model():
    """Import and initialize faster-whisper model"""
    try:
        from faster_whisper import WhisperModel
        return WhisperModel
    except ImportError:
        print("Error: faster-whisper not found. Install it in your venv: pip install faster-whisper")
        sys.exit(1)

def transcribe_audio(audio_path, model_size="base", device="cpu", output_format="text"):
    """Transcribe audio file and return results"""
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    print(f"Loading {model_size} model...")
    WhisperModel = get_whisper_model()
    model = WhisperModel(model_size, device=device, compute_type="int8")
    
    print(f"Transcribing {audio_path}...")
    segments, info = model.transcribe(audio_path)
    
    # Collect results
    results = {
        "file": audio_path,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration if hasattr(info, 'duration') else None,
        "segments": [],
        "full_text": ""
    }
    
    full_text_parts = []
    
    for segment in segments:
        segment_data = {
            "start": round(segment.start, 2),
            "end": round(segment.end, 2), 
            "text": segment.text.strip()
        }
        results["segments"].append(segment_data)
        full_text_parts.append(segment.text.strip())
    
    results["full_text"] = " ".join(full_text_parts)
    
    return results

def format_output(results, format_type="text"):
    """Format transcription results"""
    
    if format_type == "json":
        return json.dumps(results, indent=2)
    
    elif format_type == "srt":
        # SRT subtitle format
        srt_content = ""
        for i, segment in enumerate(results["segments"], 1):
            start_time = format_timestamp_srt(segment["start"])
            end_time = format_timestamp_srt(segment["end"])
            srt_content += f"{i}\n{start_time} --> {end_time}\n{segment['text']}\n\n"
        return srt_content
    
    else:  # text format (default)
        output = []
        output.append(f"🎤 Transcription: {os.path.basename(results['file'])}")
        output.append(f"🗣️  Language: {results['language']} (confidence: {results['language_probability']:.2f})")
        if results['duration']:
            output.append(f"⏱️  Duration: {results['duration']:.1f}s")
        output.append("-" * 50)
        
        for segment in results["segments"]:
            output.append(f"[{segment['start']:.2f}s → {segment['end']:.2f}s] {segment['text']}")
        
        output.append("-" * 50)
        output.append("📝 Full Text:")
        output.append(results["full_text"])
        
        return "\n".join(output)

def format_timestamp_srt(seconds):
    """Convert seconds to SRT timestamp format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def main():
    parser = argparse.ArgumentParser(description="Transcribe voice messages with faster-whisper")
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument("--model", default="base", 
                       choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                       help="Whisper model size (default: base)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                       help="Device to use (default: cpu)")
    parser.add_argument("--format", default="text", choices=["text", "json", "srt"],
                       help="Output format (default: text)")
    parser.add_argument("--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    try:
        # Transcribe
        results = transcribe_audio(args.audio_file, args.model, args.device)
        
        # Format output
        formatted = format_output(results, args.format)
        
        # Output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted)
            print(f"Transcription saved to: {args.output}")
        else:
            print(formatted)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure we can import faster_whisper by running in the right environment
    if WHISPER_PYTHON.exists() and "whisper-env" not in sys.executable:
        # Re-run this script with the whisper environment Python
        import subprocess
        cmd = [str(WHISPER_PYTHON)] + sys.argv
        subprocess.run(cmd)
    else:
        main()