"""
Video Module API URLs.
"""

from django.urls import path
from .views import VideoConvertView, VideoTrimView, VideoInfoView

app_name = 'video'

urlpatterns = [
    path('convert/', VideoConvertView.as_view(), name='convert'),
    path('trim/', VideoTrimView.as_view(), name='trim'),
    path('info/', VideoInfoView.as_view(), name='info'),
]
