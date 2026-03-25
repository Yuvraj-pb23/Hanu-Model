import time
import math
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import torch
from faster_whisper import WhisperModel
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Flat model directory: TranscriberBackend/model/
# Expected contents: model.bin, config.json,
# tokenizer.json, vocabulary.json, preprocessor_config.json
_MODEL_DIR = Path(__file__).parent / "model"


class ModelManager:
    """Manage loading and caching of faster-whisper models — LOCAL ONLY, no internet."""

    def __init__(self):
        # Cache loaded model for 1 hour; avoids reloading across requests
        self.model_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)

    def get_whisper_model(self, model_size: str = "large-v3-turbo") -> WhisperModel:
        model_key = f"whisper_{model_size}"

        if model_key in self.model_cache:
            return self.model_cache[model_key]

        # Verify model directory and model.bin exist before attempting load
        if not _MODEL_DIR.exists():
            raise FileNotFoundError(
                f"Model directory not found: '{_MODEL_DIR}'\n"
                "Place all model files (model.bin, config.json, tokenizer.json, "
                "vocabulary.json, preprocessor_config.json) inside "
                "TranscriberBackend/model/"
            )

        if not (_MODEL_DIR / "model.bin").exists():
            raise FileNotFoundError(
                f"model.bin not found in '{_MODEL_DIR}'.\n"
                "Ensure TranscriberBackend/model/model.bin exists."
            )

        model_path = str(_MODEL_DIR)

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # float16 on GPU is fastest; int8 on CPU keeps memory low without hurting quality
            compute_type = "float16" if device == "cuda" else "int8"

            # Block any accidental network calls
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

            logger.info(
                "[MODEL] Loading from: %s  |  device=%s  compute_type=%s",
                model_path, device, compute_type,
            )

            model = WhisperModel(
                model_path,
                device=device,
                compute_type=compute_type,
                local_files_only=True,
                # cpu_threads=0 lets CTranslate2 auto-select optimal thread count
                cpu_threads=0,
            )

            self.model_cache[model_key] = model
            logger.info("[MODEL] Loaded successfully.")
            return model

        except Exception as e:
            logger.error("Failed to load model from %s: %s", model_path, e)
            raise


# Shared across all requests — model is loaded once and kept in memory
model_manager = ModelManager()


class TranscriptionEngine:
    """Handle transcription using faster-whisper."""

    def __init__(self, model_size: str = "large-v3-turbo"):
        self.model_size = model_size
        self.model = None
        self.model_manager = model_manager

    def load_model(self):
        if not self.model:
            self.model = self.model_manager.get_whisper_model(self.model_size)

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
        vad_filter: bool = False,
        vad_parameters: Optional[Dict[str, Any]] = None,
        beam_size: int = 5,
        progress_callback=None,
        **kwargs
    ) -> Dict[str, Any]:
        self.load_model()
        try:
            start_time = time.time()

            # Provide an initial prompt for Hindi to strongly urge Devanagari script output
            initial_prompt = None
            if language == "hi":
                initial_prompt = "यहाँ हिंदी में बोलें। यह देवनागरी लिपि है।"

            segments_generator, info = self.model.transcribe(
                audio_path,
                language=language,
                word_timestamps=word_timestamps,
                condition_on_previous_text=False,
                initial_prompt=initial_prompt,
                beam_size=beam_size,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters or dict(min_silence_duration_ms=500),
                **kwargs
            )

            segments = []
            full_text = ""
            all_probs = []

            for segment in segments_generator:
                full_text += segment.text + " "

                seg_dict = {
                    "id": segment.id,
                    "seek": segment.seek,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "tokens": segment.tokens,
                    "temperature": segment.temperature,
                    "avg_logprob": segment.avg_logprob,
                    "compression_ratio": segment.compression_ratio,
                    "no_speech_prob": segment.no_speech_prob,
                }

                if word_timestamps and segment.words:
                    word_list = []
                    for word in segment.words:
                        word_list.append({
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        })
                        all_probs.append(word.probability)
                    seg_dict["words"] = word_list
                else:
                    all_probs.append(math.exp(segment.avg_logprob))

                segments.append(seg_dict)

            processing_time = time.time() - start_time
            confidence = float(np.mean(all_probs)) if all_probs else 0.0

            return {
                'text': full_text.strip(),
                'language': info.language,
                'segments': segments,
                'confidence': confidence,
                'processing_time': processing_time,
                'word_timestamps': word_timestamps,
            }

        except Exception as e:
            logger.error("Transcription error: %s", e)
            raise
