"""
URL configuration for Hanuai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.views.generic import RedirectView
from Website.views import custom_400, custom_403, custom_404, custom_500

urlpatterns = [
    path("administration-hanuai-dashboard/", admin.site.urls),
    path("", include("Website.urls")),
    path('captcha/', include('captcha.urls')),
    path("__reload__/", include("django_browser_reload.urls")),
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "assets/img/favicon.ico")),
]

# Serve media files even when DEBUG=False
# This allows blog images to work in production
# For better performance in production, use nginx/apache or cloud storage (S3, Cloudinary)
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

# Serve static files
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler400 = custom_400
handler403 = custom_403
handler404 = custom_404
handler500 = custom_500
