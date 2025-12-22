"""
Audio Module Template URLs.
"""

from django.urls import path
from .template_views import (
    AudioHomeView,
    AudioConvertPageView,
    AudioTrimPageView,
    VideoToAudioPageView,
)

app_name = 'audio_templates'

urlpatterns = [
    path('', AudioHomeView.as_view(), name='home'),
    path('convert/', AudioConvertPageView.as_view(), name='convert'),
    path('trim/', AudioTrimPageView.as_view(), name='trim'),
    path('extract/', VideoToAudioPageView.as_view(), name='extract'),
]
