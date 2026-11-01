#!/usr/bin/env python3
"""
Voice transcription with Ollama analysis integration
Part of the voice-transcribe skill
"""

import sys
import argparse
import json
import requests
import subprocess
from pathlib import Path
from transcribe_voice import transcribe_audio, format_output

OLLAMA_BASE_URL = "http://localhost:11434"

def check_ollama():
    """Check if Ollama is running"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
        return response.status_code == 200
    except:
        return False

def ollama_chat(model, prompt, system_prompt=None):
    """Send chat request to Ollama"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["message"]["content"]
    except Exception as e:
        return f"Error: {e}"

def analyze_transcription(text, analysis_type="summary", model="qwen3:8b"):
    """Analyze transcription with Ollama"""
    
    prompts = {
        "summary": "Provide a concise summary of this transcription, highlighting the key points:",
        "action_items": "Extract any action items, tasks, or follow-ups mentioned in this transcription:",
        "sentiment": "Analyze the sentiment and tone of this transcription:",
        "key_points": "List the main key points from this transcription:",
        "translation": "Translate this transcription to English (if not already in English):"
    }
    
    system_prompts = {
        "summary": "You are a helpful assistant that creates clear, concise summaries.",
        "action_items": "You extract actionable items from conversations and present them clearly.",
        "sentiment": "You analyze sentiment and tone in a balanced, professional way.",
        "key_points": "You identify and organize key information clearly.",
        "translation": "You provide accurate translations while preserving meaning and context."
    }
    
    if analysis_type not in prompts:
        return f"Unknown analysis type: {analysis_type}"
    
    prompt = f"{prompts[analysis_type]}\n\nTranscription:\n{text}"
    system_prompt = system_prompts.get(analysis_type)
    
    return ollama_chat(model, prompt, system_prompt)

def enhance_transcription(text, model="qwen3:8b"):
    """Enhance transcription by fixing common speech-to-text errors"""
    system_prompt = """You are a transcription enhancement assistant. Your job is to:
1. Fix obvious speech-to-text errors while preserving the original meaning
2. Add proper punctuation and capitalization
3. Maintain the speaker's original voice and style
4. Only make changes that clearly improve accuracy
5. Do not add content that wasn't in the original"""
    
    prompt = f"Please enhance this transcription by fixing errors and improving formatting:\n\n{text}"
    
    return ollama_chat(model, prompt, system_prompt)

def main():
    parser = argparse.ArgumentParser(description="Transcribe and analyze voice messages")
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument("--model", default="base", 
                       choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                       help="Whisper model size (default: base)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                       help="Device to use (default: cpu)")
    
    # Analysis options
    parser.add_argument("--analyze", action="store_true", help="Perform analysis with Ollama")
    parser.add_argument("--analysis-type", default="summary",
                       choices=["summary", "action_items", "sentiment", "key_points", "translation"],
                       help="Type of analysis (default: summary)")
    parser.add_argument("--enhance", action="store_true", help="Enhance transcription quality")
    parser.add_argument("--ollama-model", default="qwen3:8b", help="Ollama model for analysis")
    
    parser.add_argument("--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    try:
        print("🎤 Transcribing audio...")
        results = transcribe_audio(args.audio_file, args.model, args.device)
        
        # Start building output
        output_sections = []
        
        # Basic transcription
        output_sections.append("=" * 60)
        output_sections.append("📝 TRANSCRIPTION")
        output_sections.append("=" * 60)
        output_sections.append(format_output(results, "text"))
        
        # Ollama analysis if requested
        if (args.analyze or args.enhance) and not check_ollama():
            output_sections.append("\n⚠️  Ollama not available - skipping analysis")
        elif args.analyze or args.enhance:
            text = results["full_text"]
            
            if args.enhance:
                output_sections.append("\n" + "=" * 60)
                output_sections.append("✨ ENHANCED TRANSCRIPTION")
                output_sections.append("=" * 60)
                enhanced = enhance_transcription(text, args.ollama_model)
                output_sections.append(enhanced)
                text = enhanced  # Use enhanced version for further analysis
            
            if args.analyze:
                output_sections.append("\n" + "=" * 60)
                output_sections.append(f"🧠 ANALYSIS ({args.analysis_type.upper()})")
                output_sections.append("=" * 60)
                analysis = analyze_transcription(text, args.analysis_type, args.ollama_model)
                output_sections.append(analysis)
        
        # Final output
        final_output = "\n".join(output_sections)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(final_output)
            print(f"\nResults saved to: {args.output}")
        else:
            print(final_output)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()