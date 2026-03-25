# main.py

import os
import tempfile
import subprocess
import time
import json
import logging
import warnings
import asyncio
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import traceback
from pathlib import Path
import uuid

import numpy as np
import torch
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import pydub
import gtts
from deep_translator import GoogleTranslator
import whisper
import librosa
import soundfile as sf
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import joblib
from cachetools import TTLCache

# Added scipy for advanced audio filtering (Telephone, Radio, Underwater effects)
from scipy import signal

# --- Environment and Logging Setup ---
warnings.filterwarnings("ignore")
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audio_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
class Config:
    MAX_FILE_SIZE = 5000 * 1024 * 1024  
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'flac', 'ogg', 'mp4', 'avi', 'mov', 'mkv', 'webm'}
    SAMPLE_RATE = 16000
    MODELS_DIR = "models"
    CACHE_DIR = "cache"
    OUTPUT_DIR = "outputs"
    MAX_WORKERS = 10
    CACHE_MAX_SIZE = 1000
    CACHE_TTL = 36000  

config = Config()

# Create necessary directories
for dir_path in [config.MODELS_DIR, config.CACHE_DIR, config.OUTPUT_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# --- Language Dictionary ---
LANGUAGE_DICT = {
    "af": "Afrikaans", "sq": "Albanian", "am": "Amharic", "ar": "Arabic", "hy": "Armenian",
    "az": "Azerbaijani", "eu": "Basque", "be": "Belarusian", "bn": "Bengali", "bs": "Bosnian",
    "bg": "Bulgarian", "ca": "Catalan", "ceb": "Cebuano", "zh": "Chinese", "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)", "co": "Corsican", "hr": "Croatian", "cs": "Czech", "da": "Danish",
    "nl": "Dutch", "en": "English", "eo": "Esperanto", "et": "Estonian", "fi": "Finnish",
    "fr": "French", "fy": "Frisian", "gl": "Galician", "ka": "Georgian", "de": "German",
    "el": "Greek", "gu": "Gujarati", "ht": "Haitian Creole", "ha": "Hausa", "haw": "Hawaiian",
    "he": "Hebrew", "hi": "Hindi", "hmn": "Hmong", "hu": "Hungarian", "is": "Icelandic",
    "ig": "Igbo", "id": "Indonesian", "ga": "Irish", "it": "Italian", "ja": "Japanese",
    "jv": "Javanese", "kn": "Kannada", "kk": "Kazakh", "km": "Khmer", "rw": "Kinyarwanda",
    "ko": "Korean", "ku": "Kurdish", "ky": "Kyrgyz", "lo": "Lao", "la": "Latin", "lv": "Latvian",
    "lt": "Lithuanian", "lb": "Luxembourgish", "mk": "Macedonian", "mg": "Malagasy", "ms": "Malay",
    "ml": "Malayalam", "mt": "Maltese", "mi": "Maori", "mr": "Marathi", "mn": "Mongolian",
    "my": "Myanmar (Burmese)", "ne": "Nepali", "no": "Norwegian", "ny": "Nyanja", "or": "Odia",
    "ps": "Pashto", "fa": "Persian", "pl": "Polish", "pt": "Portuguese", "pa": "Punjabi",
    "ro": "Romanian", "ru": "Russian", "sm": "Samoan", "gd": "Scots Gaelic", "sr": "Serbian",
    "st": "Sesotho", "sn": "Shona", "sd": "Sindhi", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali", "es": "Spanish", "su": "Sundanese", "sw": "Swahili",
    "sv": "Swedish", "tl": "Tagalog", "tg": "Tajik", "ta": "Tamil", "tt": "Tatar", "te": "Telugu",
    "th": "Thai", "tr": "Turkish", "tk": "Turkmen", "uk": "Ukrainian", "ur": "Urdu",
    "ug": "Uyghur", "uz": "Uzbek", "vi": "Vietnamese", "cy": "Welsh", "xh": "Xhosa",
    "yi": "Yiddish", "yo": "Yoruba", "zu": "Zulu", "auto": "Auto Detect"
}

# --- Voice Configuration (Expanded) ---
VOICE_STYLES = {
    "neutral": {"rate": 1.0, "pitch": 0, "volume": 1.0, "emphasis": "normal"},
    "excited": {"rate": 1.3, "pitch": 100, "volume": 1.1, "emphasis": "high"},
    "calm": {"rate": 0.8, "pitch": -100, "volume": 0.9, "emphasis": "low"},
    "professional": {"rate": 1.1, "pitch": 0, "volume": 1.0, "emphasis": "medium"},
    "storytelling": {"rate": 0.9, "pitch": 50, "volume": 1.05, "emphasis": "medium"},
    "fast": {"rate": 1.5, "pitch": 0, "volume": 1.0, "emphasis": "normal"},
    "slow": {"rate": 0.7, "pitch": -50, "volume": 0.95, "emphasis": "low"},
    "robot": {"rate": 1.0, "pitch": 300, "volume": 0.8, "emphasis": "high", "effect": "robot"},
    "echo": {"rate": 1.0, "pitch": 0, "volume": 1.0, "emphasis": "normal", "effect": "echo"},
    "whisper": {"rate": 0.9, "pitch": 200, "volume": 0.6, "emphasis": "low", "effect": "whisper"},
    
    # New Styles
    "cheerful": {"rate": 1.2, "pitch": 150, "volume": 1.1, "emphasis": "high"},
    "sad": {"rate": 0.85, "pitch": -120, "volume": 0.85, "emphasis": "low"},
    "angry": {"rate": 1.1, "pitch": -50, "volume": 1.2, "emphasis": "high", "effect": "distortion"},
    "scared": {"rate": 1.1, "pitch": 200, "volume": 0.9, "emphasis": "high", "effect": "tremolo"},
    "news": {"rate": 1.15, "pitch": -20, "volume": 1.0, "emphasis": "medium"},
    "dramatic": {"rate": 0.95, "pitch": 80, "volume": 1.2, "emphasis": "dynamic"},
    "radio_dj": {"rate": 1.1, "pitch": 20, "volume": 1.1, "effect": "radio"},
    "telephone": {"rate": 1.0, "pitch": 0, "volume": 0.9, "effect": "telephone"},
    "underwater": {"rate": 0.9, "pitch": -100, "volume": 0.8, "effect": "underwater"}
}

# Predefined voice profiles (Expanded)
VOICE_PROFILES = {
    "standard": {
        "gender": "neutral",
        "age": "adult",
        "accent": "neutral",
        "temperament": "calm"
    },
    "news_anchor": {
        "gender": "any",
        "age": "adult",
        "accent": "standard",
        "temperament": "authoritative",
        "rate": 1.1,
        "pitch": -50,
        "style": "news"
    },
    "storyteller": {
        "gender": "any",
        "age": "mature",
        "accent": "warm",
        "temperament": "expressive",
        "rate": 0.9,
        "pitch": 30,
        "style": "storytelling"
    },
    "assistant": {
        "gender": "neutral",
        "age": "young",
        "accent": "friendly",
        "temperament": "helpful",
        "rate": 1.0,
        "pitch": 100,
        "style": "cheerful"
    },
    "dramatic": {
        "gender": "any",
        "age": "any",
        "accent": "theatrical",
        "temperament": "emotional",
        "rate": 1.2,
        "pitch": 150,
        "volume": 1.2,
        "style": "dramatic"
    },
    # New Profiles
    "elderly": {
        "gender": "any",
        "age": "senior",
        "accent": "soft",
        "temperament": "slow",
        "rate": 0.75,
        "pitch": -150,
        "volume": 0.9
    },
    "teenager": {
        "gender": "any",
        "age": "teen",
        "accent": "casual",
        "temperament": "energetic",
        "rate": 1.3,
        "pitch": 150,
        "volume": 1.0
    },
    "giant": {
        "gender": "male",
        "age": "ancient",
        "accent": "booming",
        "temperament": "slow",
        "rate": 0.6,
        "pitch": -250,
        "volume": 1.3
    },
    "pixie": {
        "gender": "female",
        "age": "young",
        "accent": "high",
        "temperament": "fast",
        "rate": 1.6,
        "pitch": 300,
        "volume": 0.9
    },
    "radio_announcer": {
        "gender": "male",
        "age": "adult",
        "accent": "projected",
        "temperament": "loud",
        "rate": 1.1,
        "pitch": -20,
        "volume": 1.2,
        "effect": "radio",
        "style": "radio_dj"
    },
    "mysterious": {
        "gender": "any",
        "age": "adult",
        "accent": "whispery",
        "temperament": "quiet",
        "rate": 0.85,
        "pitch": -50,
        "volume": 0.8,
        "effect": "underwater"
    }
}

# Download NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# --- Helper Functions ---
def check_ffmpeg_installed() -> bool:
    """Check if ffmpeg is installed and accessible."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
        logger.info("FFmpeg is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"FFmpeg not found: {e}")
        return False

def convert_to_wav(input_path: str, output_path: str, sample_rate: int = 16000) -> bool:
    """Convert any audio/video file to WAV format."""
    try:
        cmd = [
            "ffmpeg", "-i", input_path,
            "-ac", "1",  # Mono
            "-ar", str(sample_rate),  # Sample rate
            "-acodec", "pcm_s16le",  # Codec
            "-y", output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Audio conversion successful: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        return False

def extract_audio_features(audio_path: str) -> Dict[str, Any]:
    """Extract audio features for analysis."""
    try:
        y, sr = librosa.load(audio_path, sr=config.SAMPLE_RATE)
        
        features = {
            "duration": float(librosa.get_duration(y=y, sr=sr)),
            "sample_rate": sr,
            "channels": 1 if y.ndim == 1 else y.shape[0],
            "rms_energy": float(np.mean(librosa.feature.rms(y=y))),
            "zero_crossing_rate": float(np.mean(librosa.feature.zero_crossing_rate(y=y))),
            "spectral_centroid": float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
            "spectral_bandwidth": float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))),
            "tempo": float(librosa.beat.tempo(y=y, sr=sr)[0]),
        }
        
        return features
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        return {}

def detect_language(text: str) -> str:
    """Detect language of text."""
    try:
        if len(text) < 20:
            return "en"
        # Simple detection based on unicode ranges (fallback)
        if any('\u0600' <= c <= '\u06FF' for c in text): return "ar"
        elif any('\u4e00' <= c <= '\u9fff' for c in text): return "zh-CN"
        elif any('\u3040' <= c <= '\u309F' for c in text): return "ja"
        elif any('\uAC00' <= c <= '\uD7A3' for c in text): return "ko"
        elif any('\u0400' <= c <= '\u04FF' for c in text): return "ru"
        else: return "en"
    except:
        return "en"

def apply_audio_effects(audio_data: np.ndarray, sample_rate: int, effects: Dict[str, Any]) -> np.ndarray:
    """Apply various audio effects to the audio data."""
    try:
        y = audio_data.copy()
        
        # Rate adjustment (speed)
        if 'rate' in effects and effects['rate'] != 1.0:
            rate = max(0.5, min(2.0, effects['rate']))
            if rate != 1.0:
                y = librosa.effects.time_stretch(y, rate=rate)
        
        # Pitch adjustment
        if 'pitch' in effects and effects['pitch'] != 0:
            pitch_shift = effects['pitch'] / 100.0  # Convert cents to semitones
            y = librosa.effects.pitch_shift(y, sr=sample_rate, n_steps=pitch_shift)
        
        # Volume adjustment
        if 'volume' in effects:
            y = y * effects['volume']
        
        # Apply audio effects
        if 'effect' in effects:
            effect_type = effects['effect']
            
            if effect_type == 'echo':
                # Simple echo effect
                echo = np.zeros_like(y)
                delay = int(sample_rate * 0.3) 
                echo[delay:] = y[:-delay] * 0.5
                y = y + echo
                
            elif effect_type == 'robot':
                # Robot voice effect (vocal tract length perturbation)
                y = librosa.effects.pitch_shift(y, sr=sample_rate, n_steps=4)
                # Add some distortion
                y = np.tanh(y * 3) * 0.7
                
            elif effect_type == 'whisper':
                # Whisper effect
                y = y * 0.6  # Reduce volume
                # Add some breathiness
                noise = np.random.normal(0, 0.005, len(y))
                y = y + noise

            elif effect_type == 'telephone':
                # Bandpass filter (300Hz to 3400Hz)
                nyq = 0.5 * sample_rate
                low = 300 / nyq
                high = 3400 / nyq
                b, a = signal.butter(4, [low, high], btype='band')
                y = signal.filtfilt(b, a, y)
                # Add slight compression
                y = np.tanh(y * 1.5) * 0.8

            elif effect_type == 'radio':
                # Bandpass with higher cutoffs + slight noise
                nyq = 0.5 * sample_rate
                low = 400 / nyq
                high = 4000 / nyq
                b, a = signal.butter(4, [low, high], btype='band')
                y = signal.filtfilt(b, a, y)
                # Add static noise
                noise = np.random.normal(0, 0.002, len(y))
                y = y + noise
                # Compression
                y = np.tanh(y * 2.0) * 0.8

            elif effect_type == 'underwater':
                # Lowpass filter (muffle sound)
                nyq = 0.5 * sample_rate
                cutoff = 800 / nyq
                b, a = signal.butter(4, cutoff, btype='low')
                y = signal.filtfilt(b, a, y)
                # Add resonance/comb filter simulation
                delay = int(sample_rate * 0.02) # 20ms
                y[delay:] = y[delay:] + y[:-delay] * 0.5

            elif effect_type == 'distortion':
                y = np.tanh(y * 3.0) * 0.8
            
            elif effect_type == 'tremolo':
                # Amplitude modulation
                t = np.linspace(0, len(y)/sample_rate, len(y))
                modulator = 1.0 + 0.5 * np.sin(2 * np.pi * 10.0 * t) # 10Hz tremolo
                y = y * modulator

        # Equalizer adjustment
        if 'equalizer' in effects:
            eq_settings = effects['equalizer']
            nyq = 0.5 * sample_rate
            
            if 'bass' in eq_settings and eq_settings['bass'] != 1.0:
                b, a = signal.butter(4, 250/nyq, 'low')
                filtered = signal.filtfilt(b, a, y)
                y = y + (filtered * (eq_settings['bass'] - 1.0))
            
            if 'treble' in eq_settings and eq_settings['treble'] != 1.0:
                b, a = signal.butter(4, 4000/nyq, 'high')
                filtered = signal.filtfilt(b, a, y)
                y = y + (filtered * (eq_settings['treble'] - 1.0))
        
        # Normalize audio
        y = np.clip(y, -1.0, 1.0)
        if np.max(np.abs(y)) > 0:
            y = y / np.max(np.abs(y)) * 0.95  # Normalize to 95% to avoid clipping
        
        return y
        
    except Exception as e:
        logger.error(f"Audio effects failed: {e}")
        import traceback
        traceback.print_exc()
        return audio_data

# --- Model Management ---
class ModelManager:
    """Manage loading and caching of models."""
    
    def __init__(self):
        self.models = {}
        self.model_cache = TTLCache(maxsize=10, ttl=3600)
    
    def get_whisper_model(self, model_size: str = "small") -> whisper.Whisper:
        model_key = f"whisper_{model_size}"
        
        if model_key in self.model_cache:
            return self.model_cache[model_key]
        
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading Whisper {model_size} on {device}")
            model = whisper.load_model(model_size, device=device)
            self.model_cache[model_key] = model
            logger.info(f"Whisper {model_size} loaded successfully")
            return model
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

# --- Processing Classes ---

class AudioProcessor:
    """Handle audio processing tasks."""
    
    def __init__(self):
        pass
    
    def process_audio_file(self, file_path: str, audio_bytes: bytes = None) -> Dict[str, Any]:
        """Process audio file and extract features."""
        try:
            if audio_bytes:
                temp_path = f"/tmp/audio_{uuid.uuid4()}.wav"
                with open(temp_path, 'wb') as f:
                    f.write(audio_bytes)
                file_path = temp_path
            
            features = extract_audio_features(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else len(audio_bytes) if audio_bytes else 0
            
            return {
                "file_info": {
                    "path": file_path,
                    "size": file_size,
                    "duration": features.get("duration", 0),
                },
                "features": features,
                "status": "processed"
            }
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            raise

class TranscriptionEngine:
    """Handle transcription using Whisper."""
    
    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self.model = None
        self.model_manager = ModelManager()
    
    def load_model(self):
        if not self.model:
            self.model = self.model_manager.get_whisper_model(self.model_size)
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
        progress_callback=None,
        **kwargs
    ) -> Dict[str, Any]:
        self.load_model()
        try:
            start_time = time.time()
            
            # Transcribe
            result = self.model.transcribe(
                audio_path,
                language=language,
                word_timestamps=word_timestamps,
                fp16=torch.cuda.is_available(),
                **kwargs
            )
            
            processing_time = time.time() - start_time
            
            # Calculate confidence scores
            confidence = 0.0
            if result.get('segments'):
                all_probs = []
                for segment in result['segments']:
                    if 'words' in segment:
                        all_probs.extend([w.get('probability', 0.0) for w in segment['words']])
                    elif 'probabilities' in segment:
                        all_probs.append(segment.get('avg_logprob', 0.0))
                if all_probs:
                    confidence = float(np.mean(all_probs))
            
            transcription_result = {
                'text': result.get('text', '').strip(),
                'language': result.get('language', language or 'en'),
                'segments': result.get('segments', []),
                'confidence': confidence,
                'processing_time': processing_time,
                'word_timestamps': word_timestamps
            }
            return transcription_result
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

class TranslationEngine:
    """Handle text translation."""
    
    def __init__(self):
        self.cache = TTLCache(maxsize=config.CACHE_MAX_SIZE, ttl=config.CACHE_TTL)
    
    def translate_text(
        self,
        text: str,
        target_lang: str,
        source_lang: str = "auto"
    ) -> Dict[str, Any]:
        if not text or not text.strip():
            return {"translated_text": "", "source_lang": source_lang, "target_lang": target_lang}
        
        if target_lang == source_lang or target_lang == "auto":
            return {"translated_text": text, "source_lang": source_lang, "target_lang": target_lang}
        
        # Check cache
        cache_key = f"{source_lang}_{target_lang}_{hash(text)}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            start_time = time.time()
            if source_lang == "auto":
                detected_lang = detect_language(text)
                source_lang = detected_lang
            
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated_text = translator.translate(text)
            
            result = {
                "translated_text": translated_text,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "processing_time": time.time() - start_time
            }
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise

class SummaryEngine:
    """Handle text summarization."""
    
    def __init__(self):
        self.cache = TTLCache(maxsize=config.CACHE_MAX_SIZE, ttl=config.CACHE_TTL)
    
    def extractive_summary(self, text: str, ratio: float = 0.3) -> str:
        try:
            sentences = sent_tokenize(text)
            if len(sentences) <= 1: return text
            
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(sentences)
            sentence_scores = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])[0]
            ranked_sentences = sorted(
                ((sentence_scores[i], sentences[i]) for i in range(len(sentence_scores))), reverse=True
            )
            num_sentences = max(1, int(len(sentences) * ratio))
            summary_sentences = [sent for _, sent in ranked_sentences[:num_sentences]]
            return " ".join(summary_sentences)
        except Exception as e:
            logger.error(f"Extractive summary failed: {e}")
            return text[:500] + "..." if len(text) > 500 else text
    
    def summarize(self, text: str, ratio: float = 0.3, summary_type: str = "extractive") -> Dict[str, Any]:
        start_time = time.time()
        try:
            if not text or len(text.strip()) < 100:
                return {"summary": text, "original_length": len(text), "processing_time": 0.0}
            
            summary = self.extractive_summary(text, ratio)
            processing_time = time.time() - start_time
            
            result = {
                "summary": summary,
                "original_length": len(text),
                "summary_length": len(summary),
                "compression_ratio": len(summary) / len(text) if text else 0,
                "summary_type": summary_type,
                "processing_time": processing_time
            }
            return result
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise

class AdvancedTTSEngine:
    """Advanced Text-to-Speech with multiple voices and voice modulation."""
    
    def __init__(self):
        # Cache for generated audio
        self.cache = TTLCache(maxsize=200, ttl=7200)
        
        # Voice database with characteristics (Expanded: Distinct Sounds)
        self.voice_database = {
            # --- ENGLISH ---
            "en-male-standard": {
                "language": "en", "gender": "male", "age": "adult", "accent": "neutral",
                "pitch": -80, "rate": 1.0, "volume": 1.0
            },
            "en-female-standard": {
                "language": "en", "gender": "female", "age": "adult", "accent": "neutral",
                "pitch": 130, "rate": 1.05, "volume": 1.0
            },
            "en-child": {
                "language": "en", "gender": "neutral", "age": "child", "accent": "playful",
                "pitch": 300, "rate": 1.5, "volume": 0.9, "treble_boost": 1.5
            },
            
            # --- SPANISH ---
            "es-male-standard": {
                "language": "es", "gender": "male", "age": "adult", "accent": "castilian",
                "pitch": -70, "rate": 1.0, "volume": 1.0
            },
            "es-female-standard": {
                "language": "es", "gender": "female", "age": "adult", "accent": "castilian",
                "pitch": 130, "rate": 1.05, "volume": 1.0
            },
            "es-news-announcer": {
                "language": "es", "gender": "male", "age": "adult", "accent": "projected",
                "pitch": -30, "rate": 1.1, "volume": 1.2, "effect": "radio"
            },

            # --- FRENCH ---
            "fr-male-standard": {
                "language": "fr", "gender": "male", "age": "adult", "accent": "parisian",
                "pitch": -60, "rate": 1.0, "volume": 1.0
            },
            "fr-female-elegant": {
                "language": "fr", "gender": "female", "age": "adult", "accent": "parisian",
                "pitch": 120, "rate": 1.0, "volume": 1.0
            },
            "fr-elderly-female": {
                "language": "fr", "gender": "female", "age": "senior", "accent": "raspy",
                "pitch": -250, "rate": 0.75, "volume": 0.9, "effect": "underwater"
            },

            # --- GERMAN ---
            "de-male-standard": {
                "language": "de", "gender": "male", "age": "adult", "accent": "standard",
                "pitch": -70, "rate": 1.0, "volume": 1.0
            },
            "de-female-standard": {
                "language": "de", "gender": "female", "age": "adult", "accent": "standard",
                "pitch": 110, "rate": 1.0, "volume": 1.0
            },
            "de-young-boy": {
                "language": "de", "gender": "male", "age": "teen", "accent": "casual",
                "pitch": 200, "rate": 1.4, "volume": 1.0
            },

            # --- ITALIAN ---
            "it-male-standard": {
                "language": "it", "gender": "male", "age": "adult", "accent": "standard",
                "pitch": -70, "rate": 1.0, "volume": 1.0
            },
            "it-female-elegant": {
                "language": "it", "gender": "female", "age": "adult", "accent": "musical",
                "pitch": 140, "rate": 0.95, "volume": 1.0
            },
            "it-young-teen": {
                "language": "it", "gender": "female", "age": "teen", "accent": "casual",
                "pitch": 180, "rate": 1.3, "volume": 0.95
            },

            # --- PORTUGUESE ---
            "pt-male-brazil": {
                "language": "pt", "gender": "male", "age": "adult", "accent": "brazilian",
                "pitch": -60, "rate": 1.0, "volume": 1.0
            },
            "pt-female-brazil": {
                "language": "pt", "gender": "female", "age": "adult", "accent": "brazilian",
                "pitch": 120, "rate": 1.05, "volume": 1.0
            },
            "pt-child": {
                "language": "pt", "gender": "neutral", "age": "child", "accent": "playful",
                "pitch": 300, "rate": 1.5, "volume": 0.9
            },

            # --- HINDI ---
            "hi-male-standard": {
                "language": "hi", "gender": "male", "age": "adult", "accent": "standard",
                "pitch": -80, "rate": 1.0, "volume": 1.0
            },
            "hi-female-standard": {
                "language": "hi", "gender": "female", "age": "adult", "accent": "standard",
                "pitch": 120, "rate": 1.0, "volume": 1.0
            },
            "hi-elderly": {
                "language": "hi", "gender": "male", "age": "senior", "accent": "traditional",
                "pitch": -250, "rate": 0.7, "volume": 0.9, "effect": "underwater"
            },

            # --- JAPANESE ---
            "ja-male-standard": {
                "language": "ja", "gender": "male", "age": "adult", "accent": "tokyo",
                "pitch": -100, "rate": 1.0, "volume": 1.0
            },
            "ja-female-standard": {
                "language": "ja", "gender": "female", "age": "adult", "accent": "tokyo",
                "pitch": 150, "rate": 1.05, "volume": 1.0
            },
            "ja-anime-fan": {
                "language": "ja", "gender": "female", "age": "young", "accent": "anime",
                "pitch": 300, "rate": 1.2, "volume": 0.9, "treble_boost": 1.5
            },

            # --- CHINESE ---
            "zh-male-standard": {
                "language": "zh-CN", "gender": "male", "age": "adult", "accent": "mandarin",
                "pitch": -80, "rate": 1.0, "volume": 1.0
            },
            "zh-female-standard": {
                "language": "zh-CN", "gender": "female", "age": "adult", "accent": "mandarin",
                "pitch": 120, "rate": 1.0, "volume": 1.0
            },
            "zh-child": {
                "language": "zh-CN", "gender": "neutral", "age": "child", "accent": "cute",
                "pitch": 300, "rate": 1.5, "volume": 0.9, "treble_boost": 1.5
            },

            # --- RUSSIAN ---
            "ru-male-standard": {
                "language": "ru", "gender": "male", "age": "adult", "accent": "moscow",
                "pitch": -80, "rate": 1.0, "volume": 1.0
            },
            "ru-female-standard": {
                "language": "ru", "gender": "female", "age": "adult", "accent": "moscow",
                "pitch": 140, "rate": 1.0, "volume": 1.0
            },
            "ru-deep-authority": {
                "language": "ru", "gender": "male", "age": "senior", "accent": "booming",
                "pitch": -250, "rate": 0.7, "volume": 1.2, "effect": "distortion"
            },

            # --- ARABIC ---
            "ar-male-standard": {
                "language": "ar", "gender": "male", "age": "adult", "accent": "standard",
                "pitch": -80, "rate": 1.0, "volume": 1.0
            },
            "ar-female-standard": {
                "language": "ar", "gender": "female", "age": "adult", "accent": "standard",
                "pitch": 120, "rate": 1.0, "volume": 1.0
            },
            "ar-news-reader": {
                "language": "ar", "gender": "male", "age": "adult", "accent": "projected",
                "pitch": -40, "rate": 1.1, "volume": 1.2, "effect": "radio"
            },
            
            # --- SPECIAL ENGLISH PERSONAS (Distinct Fun extras) ---
            "en-robot-v2": {
                "language": "en", "gender": "neutral", "age": "any", "accent": "mechanical",
                "pitch": 400, "rate": 1.0, "volume": 0.8, "effect": "robot"
            },
            "en-telephone-man": {
                "language": "en", "gender": "male", "age": "adult", "accent": "neutral",
                "pitch": 0, "rate": 1.0, "volume": 0.9, "effect": "telephone"
            },
            "narrator-dark": {
                "language": "en", "gender": "male", "age": "mature", "accent": "mysterious",
                "pitch": -150, "rate": 0.85, "volume": 1.0, "profile": "mysterious"
            },
        }
        
        # Available voice effects (Updated)
        self.effects = {
            "echo": {"delay": 0.3, "decay": 0.5},
            "reverb": {"room_size": 0.8, "damping": 0.5},
            "robot": {"modulation": "square"},
            "whisper": {"noise_level": 0.01},
            "distortion": {"gain": 3.0},
            "telephone": {"low_cut": 300, "high_cut": 3400},
            "radio": {"low_cut": 400, "high_cut": 4000},
            "underwater": {"low_pass": 800},
            "tremolo": {"rate": 10.0, "depth": 0.5}
        }
    
    def get_available_voices(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available voices, optionally filtered by language."""
        voices = []
        for voice_id, voice_info in self.voice_database.items():
            if language and voice_info["language"] != language:
                continue
            voices.append({
                "id": voice_id,
                "name": voice_id.replace("-", " ").title(),
                **voice_info
            })
        return voices
    
    def get_voice_parameters(self, voice_id: str, modulation: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get voice parameters with optional modulation adjustments."""
        voice = self.voice_database.get(voice_id, self.voice_database["en-male-standard"])
        
        # Start with voice defaults
        params = voice.copy()
        
        # Apply modulation if provided
        if modulation:
            # Rate modulation
            if 'rate' in modulation:
                params['rate'] = max(0.5, min(2.0, params.get('rate', 1.0) * modulation['rate']))
            
            # Pitch modulation (in cents, relative to voice base pitch)
            if 'pitch' in modulation:
                params['pitch'] = params.get('pitch', 0) + modulation['pitch']
            
            # Volume modulation
            if 'volume' in modulation:
                params['volume'] = max(0.1, min(2.0, modulation['volume']))
            else:
                params['volume'] = 1.0
            
            # Apply style if specified
            if 'style' in modulation and modulation['style'] in VOICE_STYLES:
                style = VOICE_STYLES[modulation['style']]
                params['rate'] = max(0.5, min(2.0, params.get('rate', 1.0) * style['rate']))
                params['pitch'] = params.get('pitch', 0) + style['pitch']
                params['volume'] = params.get('volume', 1.0) * style['volume']
                if 'effect' in style:
                    params['effect'] = style['effect']
            
            # Apply profile if specified
            if 'profile' in modulation and modulation['profile'] in VOICE_PROFILES:
                profile = VOICE_PROFILES[modulation['profile']]
                if 'rate' in profile:
                    params['rate'] = max(0.5, min(2.0, profile['rate']))
                if 'pitch' in profile:
                    params['pitch'] = profile['pitch']
                if 'volume' in profile:
                    params['volume'] = profile['volume']
                if 'effect' in profile:
                    params['effect'] = profile['effect']
                if 'style' in profile:
                     # Apply style inside profile recursively
                     style_name = profile['style']
                     if style_name in VOICE_STYLES:
                         style = VOICE_STYLES[style_name]
                         params['rate'] = max(0.5, min(2.0, params.get('rate', 1.0) * style['rate']))
                         params['pitch'] = params.get('pitch', 0) + style['pitch']
            
            # Apply specific effects
            if 'effect' in modulation:
                params['effect'] = modulation['effect']
            
            # Apply equalizer settings
            if 'equalizer' in modulation:
                params['equalizer'] = modulation['equalizer']
        
        return params
    
    def synthesize_with_modulation(self, text: str, voice_id: str = "en-male-standard", 
                                   modulation: Dict[str, Any] = None) -> BytesIO:
        """Synthesize speech with advanced voice modulation."""
        
        cache_key = f"{voice_id}_{hash(str(modulation))}_{hash(text[:100])}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Get voice parameters with modulation
            voice_params = self.get_voice_parameters(voice_id, modulation)
            lang_code = voice_params["language"]
            
            # Generate base speech using gTTS
            slow_mode = voice_params.get('rate', 1.0) < 0.8
            tts = gtts.gTTS(text=text, lang=lang_code, slow=slow_mode)
            
            # Save to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                temp_mp3 = tmp.name
                tts.save(temp_mp3)
            
            # Load audio for processing
            y, sr = librosa.load(temp_mp3, sr=None)
            
            # Apply audio effects based on voice parameters
            effects_to_apply = {}
            
            # Rate (already handled by slow_mode in gTTS, but fine-tune if needed)
            base_rate = 0.75 if slow_mode else 1.0
            target_rate = voice_params.get('rate', 1.0)
            if target_rate != base_rate:
                effects_to_apply['rate'] = target_rate / base_rate
            
            # Pitch
            if 'pitch' in voice_params and voice_params['pitch'] != 0:
                effects_to_apply['pitch'] = voice_params['pitch']
            
            # Volume
            if 'volume' in voice_params and voice_params['volume'] != 1.0:
                effects_to_apply['volume'] = voice_params['volume']
            
            # Special effects
            if 'effect' in voice_params:
                effects_to_apply['effect'] = voice_params['effect']
            
            # Equalizer
            if 'equalizer' in voice_params:
                effects_to_apply['equalizer'] = voice_params['equalizer']
            
            # Handle Treble/Bass Boost if in voice DB (passed directly in dict)
            if 'treble_boost' in voice_params:
                effects_to_apply.setdefault('equalizer', {})['treble'] = voice_params['treble_boost']
            if 'bass_boost' in voice_params:
                effects_to_apply.setdefault('equalizer', {})['bass'] = voice_params['bass_boost']
            
            # Apply all effects
            if effects_to_apply:
                y = apply_audio_effects(y, sr, effects_to_apply)
            
            # Convert back to MP3 bytes
            audio_bytes = BytesIO()
            sf.write(audio_bytes, y, sr, format='mp3')
            audio_bytes.seek(0)
            
            # Cleanup
            os.unlink(temp_mp3)
            
            # Cache the result
            self.cache[cache_key] = audio_bytes
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Advanced TTS synthesis failed: {e}")
            # Fallback to basic gTTS
            return self.basic_synthesis(text, voice_params["language"])
    
    def basic_synthesis(self, text: str, lang: str = "en", slow: bool = False) -> BytesIO:
        """Basic TTS synthesis without modulation (fallback)."""
        try:
            tts = gtts.gTTS(text=text, lang=lang, slow=slow)
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer
        except Exception as e:
            logger.error(f"Basic TTS failed: {e}")
            raise
    
    def batch_synthesize(self, texts: List[str], voice_id: str = "en-male-standard",
                        modulation: Dict[str, Any] = None) -> List[BytesIO]:
        """Batch synthesize multiple texts."""
        results = []
        for text in texts:
            try:
                audio = self.synthesize_with_modulation(text, voice_id, modulation)
                results.append(audio)
            except Exception as e:
                logger.error(f"Failed to synthesize text: {e}")
                # Add empty bytes as placeholder for failed synthesis
                results.append(BytesIO())
        return results
    
    def get_voice_preview(self, voice_id: str, modulation: Dict[str, Any] = None) -> BytesIO:
        """Generate a preview of a voice with given modulation."""
        preview_text = "Hello, this is a preview of my voice. I can speak clearly and naturally."
        return self.synthesize_with_modulation(preview_text, voice_id, modulation)

class BatchProcessor:
    """Handle batch processing of multiple files."""
    
    def __init__(self):
        self.jobs = {}
    
    async def process_batch(
        self,
        files: List[UploadFile],
        source_lang: str = "en",
        processing_mode: str = "fast",
        output_format: str = "txt"
    ) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        
        self.jobs[job_id] = {
            "status": "processing",
            "total_files": len(files),
            "processed_files": 0,
            "results": [],
            "start_time": time.time(),
            "progress": 0
        }
        
        try:
            results = []
            successful = 0
            failed = 0
            
            for i, file in enumerate(files):
                try:
                    self.jobs[job_id]["progress"] = (i / len(files)) * 100
                    self.jobs[job_id]["processed_files"] = i
                    
                    audio_bytes = await file.read()
                    
                    # Temp files logic similar to single transcription
                    temp_dir = tempfile.mkdtemp()
                    temp_path = os.path.join(temp_dir, file.filename)
                    
                    with open(temp_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    wav_path = os.path.join(temp_dir, f"converted_{uuid.uuid4()}.wav")
                    convert_to_wav(temp_path, wav_path, config.SAMPLE_RATE)
                    
                    # Determine Model
                    if processing_mode == "fast":
                        transcriber = TranscriptionEngine("base")
                    elif processing_mode == "high_accuracy":
                        transcriber = TranscriptionEngine("medium")
                    else:
                        transcriber = TranscriptionEngine("small")
                    
                    language = None if source_lang == "auto" else source_lang
                    result = transcriber.transcribe(wav_path, language)
                    
                    result["filename"] = file.filename
                    result["file_size"] = len(audio_bytes)
                    result["success"] = True
                    results.append(result)
                    successful += 1
                    
                    # Cleanup
                    os.unlink(temp_path)
                    os.unlink(wav_path)
                    os.rmdir(temp_dir)
                    
                except Exception as e:
                    logger.error(f"Failed to process {file.filename}: {e}")
                    results.append({"filename": file.filename, "error": str(e), "success": False})
                    failed += 1
            
            total_time = time.time() - self.jobs[job_id]["start_time"]
            self.jobs[job_id].update({
                "status": "completed",
                "progress": 100,
                "processed_files": len(files),
                "total_time": total_time
            })
            
            return {
                "job_id": job_id,
                "total_files": len(files),
                "successful": successful,
                "failed": failed,
                "total_time": total_time,
                "results": results,
                "status": "completed"
            }
            
        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            raise
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        return self.jobs.get(job_id, {"error": "Job not found"})

# --- Initialize Engines ---
audio_processor = AudioProcessor()
translation_engine = TranslationEngine()
summary_engine = SummaryEngine()
tts_engine = AdvancedTTSEngine()  # Use advanced TTS engine
batch_processor = BatchProcessor()
model_manager = ModelManager()

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Audio Processing Suite API",
    description="Professional API for audio transcription, translation, and text processing with advanced TTS",
    version="4.3.0", # Updated version for distinct voices
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "4.3.0",
        "services": {
            "ffmpeg": check_ffmpeg_installed(),
            "whisper": True,
            "translation": True,
            "summarization": True,
            "tts": True,
            "voice_modulation": True
        },
        "system": {
            "cuda_available": torch.cuda.is_available(),
            "models_loaded": len(model_manager.model_cache)
        }
    }

@app.get("/api/languages")
async def get_languages():
    """Get supported languages."""
    return JSONResponse(content=LANGUAGE_DICT)

# --- Enhanced TTS Endpoints ---

@app.get("/api/tts/voices")
async def get_available_voices(
    language: str = Query(None, description="Filter voices by language code"),
    gender: str = Query(None, description="Filter voices by gender"),
    accent: str = Query(None, description="Filter voices by accent")
):
    """Get available voices with filtering options."""
    try:
        voices = tts_engine.get_available_voices(language)
        
        # Apply filters
        if gender:
            voices = [v for v in voices if v.get("gender") == gender]
        if accent:
            voices = [v for v in voices if v.get("accent") == accent]
        
        return JSONResponse(content={
            "total_voices": len(voices),
            "voices": voices
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get voices: {str(e)}")

@app.get("/api/tts/styles")
async def get_voice_styles():
    """Get available voice styles."""
    return JSONResponse(content=VOICE_STYLES)

@app.get("/api/tts/profiles")
async def get_voice_profiles():
    """Get available voice profiles."""
    return JSONResponse(content=VOICE_PROFILES)

@app.get("/api/tts/effects")
async def get_voice_effects():
    """Get available voice effects."""
    return JSONResponse(content=tts_engine.effects)

@app.post("/api/tts/advanced")
async def advanced_text_to_speech(
    text: str = Form(...),
    voice: str = Form("en-male-standard"),
    style: str = Form("neutral"),
    profile: str = Form(None),
    rate: float = Form(1.0, ge=0.5, le=2.0),
    pitch: int = Form(0, ge=-300, le=300),
    volume: float = Form(1.0, ge=0.1, le=2.0),
    effect: str = Form(None),
    bass_boost: float = Form(1.0, ge=0.5, le=2.0),
    treble_boost: float = Form(1.0, ge=0.5, le=2.0)
):
    """
    Advanced text-to-speech with voice modulation.
    
    Parameters:
    - text: Text to convert to speech
    - voice: Voice ID from available voices (e.g., 'en-male-standard', 'es-child', 'zh-female-standard')
    - style: Voice style (neutral, excited, sad, angry, news, etc.)
    - profile: Voice profile (standard, news_anchor, elderly, teenager, giant, pixie, etc.)
    - rate: Speech rate (0.5 to 2.0)
    - pitch: Pitch adjustment in cents (-300 to 300)
    - volume: Volume level (0.1 to 2.0)
    - effect: Special effect (echo, robot, whisper, telephone, radio, underwater, distortion, tremolo)
    - bass_boost: Bass frequency boost
    - treble_boost: Treble frequency boost
    """
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Limit text length
        if len(text) > 5000:
            text = text[:5000]
            logger.warning(f"Text truncated to 5000 characters for TTS")
        
        # Prepare modulation parameters
        modulation = {
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "style": style,
        }
        
        if profile:
            modulation["profile"] = profile
        
        if effect:
            modulation["effect"] = effect
        
        # Add equalizer settings
        if bass_boost != 1.0 or treble_boost != 1.0:
            modulation["equalizer"] = {
                "bass": bass_boost,
                "treble": treble_boost
            }
        
        # Generate speech with modulation
        audio_bytes = tts_engine.synthesize_with_modulation(text, voice, modulation)
        
        # Generate filename with voice and style
        timestamp = int(time.time())
        filename = f"speech_{voice}_{style}_{timestamp}.mp3"
        
        return StreamingResponse(
            audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Voice-Info": json.dumps({"voice": voice, "style": style, "modulation": modulation})
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Advanced TTS error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Advanced TTS failed: {str(e)}")

@app.get("/api/tts/preview/{voice_id}")
async def preview_voice(
    voice_id: str,
    style: str = Query("neutral"),
    rate: float = Query(1.0, ge=0.5, le=2.0),
    pitch: int = Query(0, ge=-300, le=300)
):
    """Preview a voice with specific modulation settings."""
    try:
        modulation = {
            "style": style,
            "rate": rate,
            "pitch": pitch
        }
        
        audio_bytes = tts_engine.get_voice_preview(voice_id, modulation)
        
        return StreamingResponse(
            audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=preview_{voice_id}.mp3"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice preview failed: {str(e)}")

@app.post("/api/tts/batch")
async def batch_text_to_speech(
    texts: List[str] = Form(...),
    voice: str = Form("en-male-standard"),
    style: str = Form("neutral"),
    rate: float = Form(1.0)
):
    """Batch convert multiple texts to speech."""
    try:
        if not texts or len(texts) == 0:
            raise HTTPException(status_code=400, detail="No texts provided")
        
        if len(texts) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 texts allowed per batch")
        
        modulation = {
            "style": style,
            "rate": rate
        }
        
        # Generate all audio files
        audio_files = tts_engine.batch_synthesize(texts, voice, modulation)
        
        # Create a zip file with all audio files
        import zipfile
        from fastapi.responses import Response
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, audio_bytes in enumerate(audio_files):
                if audio_bytes.getvalue():  # Skip empty files
                    filename = f"speech_{i+1}_{voice}.mp3"
                    zip_file.writestr(filename, audio_bytes.getvalue())
        
        zip_buffer.seek(0)
        
        timestamp = int(time.time())
        zip_filename = f"tts_batch_{timestamp}.zip"
        
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch TTS failed: {str(e)}")

@app.post("/api/tts/transcribe-and-speak")
async def transcribe_and_speak_advanced(
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_lang: str = Form(None),
    voice: str = Form("en-male-standard"),
    style: str = Form("neutral"),
    summary: bool = Form(False),
    summary_ratio: float = Form(0.3),
    modulation: str = Form(None)
):
    """Transcribe audio, optionally translate/summarize, and convert to speech with modulation."""
    try:
        # First, transcribe the audio
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            input_path = os.path.join(temp_dir, file.filename)
            audio_bytes = await file.read()
            with open(input_path, 'wb') as f:
                f.write(audio_bytes)
            
            # Convert to WAV
            wav_path = os.path.join(temp_dir, "audio.wav")
            if not convert_to_wav(input_path, wav_path, config.SAMPLE_RATE):
                raise HTTPException(status_code=500, detail="Audio conversion failed")
            
            # Transcribe
            transcriber = TranscriptionEngine("small")
            language = None if source_lang == "auto" else source_lang
            transcription_result = transcriber.transcribe(wav_path, language)
            text = transcription_result.get("text", "")
        
        if not text:
            raise HTTPException(status_code=400, detail="No text found in audio")
        
        # Optionally translate
        if target_lang and target_lang != source_lang:
            translation = translation_engine.translate_text(text, target_lang, source_lang)
            text = translation.get("translated_text", text)
        
        # Optionally summarize
        if summary and len(text) > 500:
            summary_result = summary_engine.summarize(text, summary_ratio)
            text = summary_result.get("summary", text)
        
        # Parse modulation if provided
        modulation_params = {}
        if modulation:
            try:
                modulation_params = json.loads(modulation)
            except:
                logger.warning(f"Invalid modulation JSON: {modulation}")
        
        # Synthesize speech with modulation
        audio_bytes = tts_engine.synthesize_with_modulation(
            text, 
            voice, 
            {**modulation_params, "style": style}
        )
        
        timestamp = int(time.time())
        filename = f"processed_{voice}_{style}_{timestamp}.mp3"
        
        return StreamingResponse(
            audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# --- Original TTS endpoint for backward compatibility ---
@app.post("/api/tts")
async def text_to_speech_endpoint(
    text: str = Form(...),
    voice: str = Form("en"),
    rate: float = Form(1.0),
    pitch: float = Form(1.0)
):
    """
    Legacy TTS endpoint for backward compatibility.
    Uses basic gTTS without advanced modulation.
    """
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Clean language code (e.g., 'en-US' -> 'en')
        lang_code = voice.split('-')[0]
        
        # Map rate to slow mode (backward compatibility)
        slow_mode = rate < 0.8
        
        # Generate speech using basic synthesis
        audio_bytes = tts_engine.basic_synthesis(text, lang_code, slow_mode)
        
        return StreamingResponse(
            audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=speech_{int(time.time())}.mp3"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Text-to-Speech failed: {str(e)}")

# --- Original endpoints (unchanged) ---

@app.post("/api/transcribe")
async def transcribe_file(
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    processing_mode: str = Form("fast"),
    segment_duration: int = Form(20),
    max_parallel_segments: int = Form(10),
    word_timestamps: bool = Form(True),
    format: str = Form("txt")
):
    """Transcribe audio/video file."""
    try:
        # Validate file
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in config.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File extension '{file_extension}' not allowed")
        
        audio_bytes = await file.read()
        file_size = len(audio_bytes)
        
        if file_size > config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size {file_size/1024/1024:.2f}MB exceeds maximum {config.MAX_FILE_SIZE/1024/1024}MB"
            )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            input_path = os.path.join(temp_dir, file.filename)
            with open(input_path, 'wb') as f:
                f.write(audio_bytes)
            
            # Convert to WAV
            wav_path = os.path.join(temp_dir, "audio.wav")
            if not convert_to_wav(input_path, wav_path, config.SAMPLE_RATE):
                raise HTTPException(status_code=500, detail="Audio conversion failed")
            
            # Extract features
            features = extract_audio_features(wav_path)
            
            # Choose Transcriber
            if processing_mode == "fast":
                transcriber = TranscriptionEngine("base")
            elif processing_mode == "high_accuracy":
                transcriber = TranscriptionEngine("medium")
            else: # normal
                transcriber = TranscriptionEngine("small")
            
            # Transcribe
            language = None if source_lang == "auto" else source_lang
            result = transcriber.transcribe(wav_path, language, word_timestamps)
            
            # Format result
            formatted_result = format_transcription_result(result, format)
            
            # Update result
            result.update({
                "filename": file.filename,
                "file_size": file_size,
                "processing_mode": processing_mode,
                "formatted_result": formatted_result
            })
            
            return JSONResponse(content=result)
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

def format_transcription_result(result: Dict[str, Any], format: str) -> str:
    text = result.get('text', '')
    segments = result.get('segments', [])
    
    if format == "txt":
        return text
    elif format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)
    elif format == "srt":
        srt_content = ""
        for i, segment in enumerate(segments, 1):
            start_time = format_time_srt(segment.get('start', 0))
            end_time = format_time_srt(segment.get('end', 0))
            t = segment.get('text', '').strip()
            srt_content += f"{i}\n{start_time} --> {end_time}\n{t}\n\n"
        return srt_content
    else:
        return text

def format_time_srt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

@app.post("/api/translate")
async def translate_text_endpoint(
    text: str = Form(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto")
):
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        result = translation_engine.translate_text(text, target_lang, source_lang)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

@app.post("/api/summarize")
async def summarize_text_endpoint(
    text: str = Form(...),
    ratio: float = Form(0.3),
    summary_type: str = Form("extractive")
):
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        if len(text) < 100:
            raise HTTPException(status_code=400, detail="Text too short (min 100 characters)")
        
        result = summary_engine.summarize(text, ratio, summary_type)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

@app.post("/api/batch/transcribe")
async def batch_transcribe_endpoint(
    files: List[UploadFile] = File(...),
    source_lang: str = Form("en"),
    processing_mode: str = Form("fast"),
    output_format: str = Form("txt")
):
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        result = await batch_processor.process_batch(files, source_lang, processing_mode, output_format)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

@app.get("/api/batch/job/{job_id}")
async def get_batch_job_status(job_id: str):
    status = batch_processor.get_job_status(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return JSONResponse(content=status)

@app.get("/api/system/stats")
async def get_system_stats():
    import psutil
    return {
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime": time.time() - psutil.boot_time()
        },
        "cache": {
            "translation": len(translation_engine.cache),
            "summary": len(summary_engine.cache),
        },
        "models": {
            "loaded": len(model_manager.model_cache),
            "available": ["tiny", "base", "small", "medium", "large"]
        },
        "tts": {
            "available_voices": len(tts_engine.voice_database),
            "cache_size": len(tts_engine.cache),
            "voice_styles": len(VOICE_STYLES),
            "voice_profiles": len(VOICE_PROFILES)
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "subscribe":
                    await websocket.send_text(json.dumps({"type": "subscribed", "message": "Subscribed to updates"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass

# --- Mount Static Files ---
# This MUST be last to allow API routes to take precedence
try:
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
except RuntimeError:
    logger.error("Static directory 'static' not found. Please create it and place index.html inside.")

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    
    if not check_ffmpeg_installed():
        logger.warning("FFmpeg is not installed. Some features may not work.")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )