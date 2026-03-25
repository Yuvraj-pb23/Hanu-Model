import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class WebsiteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Website"

    def ready(self):
        """
        Pre-warm the Whisper model when Django starts so the first
        transcription request doesn't pay the 20-30s model-load penalty.
        Runs once per process (not per request, not per thread).
        """
        # Skip pre-warming during management commands like migrations
        import sys
        if any(cmd in sys.argv for cmd in ("migrate", "makemigrations", "collectstatic", "shell")):
            return

        try:
            from TranscriberBackend.transcription import model_manager
            logger.info("[STARTUP] Pre-warming Whisper model…")
            model_manager.get_whisper_model("large-v3-turbo")
            logger.info("[STARTUP] Whisper model ready.")
        except Exception as exc:
            logger.warning("[STARTUP] Whisper pre-warm skipped: %s", exc)
