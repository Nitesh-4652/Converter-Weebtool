"""PDF Module Template Views."""
from django.views.generic import TemplateView


class PDFHomeView(TemplateView):
    template_name = 'pdf/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'PDF Tools'
        context['tools'] = [
            {'name': 'Merge PDF', 'description': 'Combine multiple PDFs into one', 'url': '/pdf/merge/', 'icon': '📎'},
            {'name': 'Split PDF', 'description': 'Split PDF into multiple files', 'url': '/pdf/split/', 'icon': '✂️'},
            {'name': 'Compress PDF', 'description': 'Reduce PDF file size', 'url': '/pdf/compress/', 'icon': '📦'},
            {'name': 'Rotate PDF', 'description': 'Rotate PDF pages', 'url': '/pdf/rotate/', 'icon': '🔄'},
            {'name': 'Protect PDF', 'description': 'Add password to PDF', 'url': '/pdf/protect/', 'icon': '🔒'},
            {'name': 'Unlock PDF', 'description': 'Remove password from PDF', 'url': '/pdf/unlock/', 'icon': '🔓'},
            {'name': 'Images to PDF', 'description': 'Convert images to PDF', 'url': '/pdf/images-to-pdf/', 'icon': '🖼️'},
            {'name': 'PDF to Images', 'description': 'Convert PDF to images', 'url': '/pdf/pdf-to-images/', 'icon': '📸'},
        ]
        return context


class PDFMergePageView(TemplateView):
    template_name = 'pdf/merge.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Merge PDF'
        return context


class PDFSplitPageView(TemplateView):
    template_name = 'pdf/split.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Split PDF'
        return context


class PDFCompressPageView(TemplateView):
    template_name = 'pdf/compress.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Compress PDF'
        return context


class PDFRotatePageView(TemplateView):
    template_name = 'pdf/rotate.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Rotate PDF'
        return context


class PDFProtectPageView(TemplateView):
    template_name = 'pdf/protect.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Protect PDF'
        return context


class PDFUnlockPageView(TemplateView):
    template_name = 'pdf/unlock.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Unlock PDF'
        return context


class ImagesToPDFPageView(TemplateView):
    template_name = 'pdf/images_to_pdf.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Images to PDF'
        return context


class PDFToImagesPageView(TemplateView):
    template_name = 'pdf/pdf_to_images.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'PDF to Images'
        return context
