"""
Core URL Configuration.
"""

from django.urls import path
from .views import (
    ConversionJobListView,
    ConversionJobDetailView,
    DownloadFileView,
)

app_name = 'core'

urlpatterns = [
    path('jobs/', ConversionJobListView.as_view(), name='job-list'),
    path('jobs/<uuid:job_id>/', ConversionJobDetailView.as_view(), name='job-detail'),
    path('download/<uuid:file_id>/', DownloadFileView.as_view(), name='download-file'),
]
