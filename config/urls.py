"""
URL configuration for converter-saas project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.views import HomeView, HealthCheckView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Home & Health
    path('', HomeView.as_view(), name='home'),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    
    # API endpoints
    path('api/core/', include('apps.core.urls')),
    path('api/audio/', include('apps.audio.urls')),
    path('api/video/', include('apps.video.urls')),
    path('api/image/', include('apps.image.urls')),
    path('api/pdf/', include('apps.pdf.urls')),
    
    # Template views
    path('audio/', include('apps.audio.template_urls')),
    path('video/', include('apps.video.template_urls')),
    path('image/', include('apps.image.template_urls')),
    path('pdf/', include('apps.pdf.template_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
