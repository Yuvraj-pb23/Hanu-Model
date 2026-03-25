"""
Custom media file serving for production when DEBUG=False
Only use this for simple deployments. For production, use nginx/apache or cloud storage.
"""

from django.views.static import serve
from django.conf import settings
import os


def serve_media(request, path):
    """
    Serve media files even when DEBUG=False
    This is a workaround for deployments where you can't configure nginx/apache
    """
    return serve(request, path, document_root=settings.MEDIA_ROOT)
