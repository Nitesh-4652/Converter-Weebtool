"""Image Module Template Views."""
from django.views.generic import TemplateView
from django.conf import settings


class ImageHomeView(TemplateView):
    template_name = 'image/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Image Tools'
        context['tools'] = [
            {
                'name': 'Image Converter',
                'description': 'Convert images between 17+ formats',
                'url': '/image/convert/',
                'icon': '🔄'
            },
            {
                'name': 'Batch Converter',
                'description': 'Convert multiple images at once with drag & drop',
                'url': '/image/batch/',
                'icon': '📦'
            },
        ]
        return context


class ImageConvertPageView(TemplateView):
    template_name = 'image/convert.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Image Converter'
        context['input_formats'] = settings.SUPPORTED_IMAGE_FORMATS
        context['output_formats'] = [
            {'value': 'jpg', 'label': 'JPEG'},
            {'value': 'png', 'label': 'PNG'},
            {'value': 'webp', 'label': 'WEBP'},
            {'value': 'gif', 'label': 'GIF'},
            {'value': 'bmp', 'label': 'BMP'},
            {'value': 'tiff', 'label': 'TIFF'},
            {'value': 'ico', 'label': 'ICO'},
        ]
        context['quality_options'] = [
            {'value': 60, 'label': 'Low (60%)'},
            {'value': 75, 'label': 'Medium (75%)'},
            {'value': 85, 'label': 'High (85%)'},
            {'value': 95, 'label': 'Best (95%)'},
        ]
        return context


class ImageBatchPageView(TemplateView):
    template_name = 'image/batch.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Batch Image Converter'
        return context

