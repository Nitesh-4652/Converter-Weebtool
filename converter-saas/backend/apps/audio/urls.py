"""
Audio Module API URLs.
"""

from django.urls import path
from .views import (
    AudioConvertView,
    AudioTrimView,
    VideoToAudioView,
    AudioInfoView,
)

app_name = 'audio'

urlpatterns = [
    path('convert/', AudioConvertView.as_view(), name='convert'),
    path('trim/', AudioTrimView.as_view(), name='trim'),
    path('extract/', VideoToAudioView.as_view(), name='extract'),
    path('info/', AudioInfoView.as_view(), name='info'),
]
