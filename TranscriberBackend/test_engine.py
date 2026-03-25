import os
import sys
import logging
from pprint import pprint

# --- IMPORTANT ---
# This script must be run BEFORE creating a FastAPI environment or using Django.
# It tests the raw engine classes directly.
from transcription import TranscriptionEngine
from translation import TranslationEngine

logging.basicConfig(level=logging.INFO)
print("Loading Transcription Engine...")
transcriber = TranscriptionEngine("small")

print("Loading Translation Engine...")
translation_engine = TranslationEngine()

print("Converting audio...")
os.system('arecord -d 2 -f cd test.wav')

print("Transcribing...")
result = transcriber.transcribe(
    'test.wav', 
    language=None, 
    word_timestamps=False
)

transcript = result.get("text", "").strip()
detected_lang = result.get("language", "Auto")

print(f"Transcript: {transcript}")
print(f"Detected language: {detected_lang}")

if transcript:
    print("Translating...")
    translation_result = translation_engine.translate_text(
        transcript, 
        target_lang="en", 
        source_lang=detected_lang
    )
    transcribed_text = translation_result.get("translated_text", transcript)
    print(f"Translation: {transcribed_text}")
