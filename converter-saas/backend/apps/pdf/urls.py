"""PDF Module API URLs."""
from django.urls import path
from .views import (
    PDFMergeView,
    PDFSplitView,
    PDFCompressView,
    PDFRotateView,
    PDFProtectView,
    PDFUnlockView,
    ImagesToPDFView,
    PDFToImagesView,
    PDFInfoView,
)

app_name = 'pdf'

urlpatterns = [
    path('merge/', PDFMergeView.as_view(), name='merge'),
    path('split/', PDFSplitView.as_view(), name='split'),
    path('compress/', PDFCompressView.as_view(), name='compress'),
    path('rotate/', PDFRotateView.as_view(), name='rotate'),
    path('protect/', PDFProtectView.as_view(), name='protect'),
    path('unlock/', PDFUnlockView.as_view(), name='unlock'),
    path('images-to-pdf/', ImagesToPDFView.as_view(), name='images-to-pdf'),
    path('pdf-to-images/', PDFToImagesView.as_view(), name='pdf-to-images'),
    path('info/', PDFInfoView.as_view(), name='info'),
]
