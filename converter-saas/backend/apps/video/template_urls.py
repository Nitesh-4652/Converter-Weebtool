"""
Video Module Template URLs.
"""

from django.urls import path
from .template_views import VideoHomeView, VideoConvertPageView, VideoTrimPageView

app_name = 'video_templates'

urlpatterns = [
    path('', VideoHomeView.as_view(), name='home'),
    path('convert/', VideoConvertPageView.as_view(), name='convert'),
    path('trim/', VideoTrimPageView.as_view(), name='trim'),
]
