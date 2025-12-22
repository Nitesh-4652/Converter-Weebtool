"""Image Module API URLs."""
from django.urls import path
from .views import ImageConvertView, ImageInfoView

app_name = 'image'

urlpatterns = [
    path('convert/', ImageConvertView.as_view(), name='convert'),
    path('info/', ImageInfoView.as_view(), name='info'),
]
