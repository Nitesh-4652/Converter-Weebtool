"""PDF Module Template URLs."""
from django.urls import path
from .template_views import (
    PDFHomeView,
    PDFMergePageView,
    PDFSplitPageView,
    PDFCompressPageView,
    PDFRotatePageView,
    PDFProtectPageView,
    PDFUnlockPageView,
    ImagesToPDFPageView,
    PDFToImagesPageView,
)

app_name = 'pdf_templates'

urlpatterns = [
    path('', PDFHomeView.as_view(), name='home'),
    path('merge/', PDFMergePageView.as_view(), name='merge'),
    path('split/', PDFSplitPageView.as_view(), name='split'),
    path('compress/', PDFCompressPageView.as_view(), name='compress'),
    path('rotate/', PDFRotatePageView.as_view(), name='rotate'),
    path('protect/', PDFProtectPageView.as_view(), name='protect'),
    path('unlock/', PDFUnlockPageView.as_view(), name='unlock'),
    path('images-to-pdf/', ImagesToPDFPageView.as_view(), name='images-to-pdf'),
    path('pdf-to-images/', PDFToImagesPageView.as_view(), name='pdf-to-images'),
]
