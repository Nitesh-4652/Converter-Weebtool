"""Image Module Template URLs."""
from django.urls import path
from .template_views import ImageHomeView, ImageConvertPageView, ImageBatchPageView

app_name = 'image_templates'

urlpatterns = [
    path('', ImageHomeView.as_view(), name='home'),
    path('convert/', ImageConvertPageView.as_view(), name='convert'),
    path('batch/', ImageBatchPageView.as_view(), name='batch'),
]

