import logging
from typing import Dict, Any
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

class TranslationEngine:
    """Handle text translation using deep_translator (Google Translate)."""
    
    def translate_text(self, text: str, target_lang: str, source_lang: str = "auto") -> Dict[str, Any]:
        try:
            if not text or not text.strip():
                return {"translated_text": "", "source_language": source_lang, "target_language": target_lang, "success": True}

            if source_lang and source_lang != "auto":
                source = source_lang.split('-')[0].lower()
            else:
                source = 'auto'
                
            target = target_lang.split('-')[0].lower()
            
            # Google Translate chunking
            max_chunk = 4500
            chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
            
            translated_chunks = []
            for chunk in chunks:
                translator = GoogleTranslator(source=source, target=target)
                translated = translator.translate(chunk)
                if translated:
                    translated_chunks.append(translated)
                
            full_translation = " ".join(translated_chunks)
            
            return {
                "translated_text": full_translation,
                "source_language": source_lang,
                "target_language": target_lang,
                "success": True
            }
        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise
