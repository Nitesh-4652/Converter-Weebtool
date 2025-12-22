"""
Video Module Template Views.
"""

from django.views.generic import TemplateView
from django.conf import settings


class VideoHomeView(TemplateView):
    template_name = 'video/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Video Tools'
        context['tools'] = [
            {
                'name': 'Video Converter',
                'description': 'Convert video files between 17+ formats',
                'url': '/video/convert/',
                'icon': '🔄'
            },
            {
                'name': 'Video Trimmer',
                'description': 'Trim video files with timeline selection',
                'url': '/video/trim/',
                'icon': '✂️'
            },
        ]
        return context


class VideoConvertPageView(TemplateView):
    template_name = 'video/convert.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Video Converter'
        context['input_formats'] = settings.SUPPORTED_VIDEO_FORMATS
        context['output_formats'] = [
            {'value': 'mp4', 'label': 'MP4'},
            {'value': 'mkv', 'label': 'MKV'},
            {'value': 'avi', 'label': 'AVI'},
            {'value': 'mov', 'label': 'MOV'},
            {'value': 'webm', 'label': 'WEBM'},
            {'value': 'flv', 'label': 'FLV'},
            {'value': 'wmv', 'label': 'WMV'},
            {'value': '3gp', 'label': '3GP'},
            {'value': 'mpg', 'label': 'MPG'},
            {'value': 'ts', 'label': 'TS'},
            {'value': 'm4v', 'label': 'M4V'},
            {'value': 'ogv', 'label': 'OGV'},
        ]
        context['resolution_options'] = [
            {'value': '1920x1080', 'label': '1080p (1920x1080)'},
            {'value': '1280x720', 'label': '720p (1280x720)'},
            {'value': '854x480', 'label': '480p (854x480)'},
            {'value': '640x360', 'label': '360p (640x360)'},
        ]
        return context


class VideoTrimPageView(TemplateView):
    template_name = 'video/trim.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Video Trimmer'
        context['input_formats'] = settings.SUPPORTED_VIDEO_FORMATS
        return context
