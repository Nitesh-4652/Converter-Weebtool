"""
Audio Module Template Views.
Django template views for audio tools.
"""

from django.views.generic import TemplateView
from django.conf import settings


class AudioHomeView(TemplateView):
    """Audio tools home page."""
    template_name = 'audio/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Audio Tools'
        context['tools'] = [
            {
                'name': 'Audio Converter',
                'description': 'Convert audio files between 15+ formats',
                'url': '/audio/convert/',
                'icon': '🔄'
            },
            {
                'name': 'Audio Trimmer',
                'description': 'Trim audio files with timeline selection',
                'url': '/audio/trim/',
                'icon': '✂️'
            },
            {
                'name': 'Video to Audio',
                'description': 'Extract audio from video files',
                'url': '/audio/extract/',
                'icon': '🎬➡️🎵'
            },
        ]
        return context


class AudioConvertPageView(TemplateView):
    """Audio conversion page."""
    template_name = 'audio/convert.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Audio Converter'
        context['input_formats'] = settings.SUPPORTED_AUDIO_FORMATS
        context['output_formats'] = [
            {'value': 'mp3', 'label': 'MP3'},
            {'value': 'wav', 'label': 'WAV'},
            {'value': 'aac', 'label': 'AAC'},
            {'value': 'm4a', 'label': 'M4A'},
            {'value': 'flac', 'label': 'FLAC'},
            {'value': 'ogg', 'label': 'OGG'},
            {'value': 'opus', 'label': 'OPUS'},
            {'value': 'aiff', 'label': 'AIFF'},
            {'value': 'wma', 'label': 'WMA'},
            {'value': 'amr', 'label': 'AMR'},
            {'value': 'ac3', 'label': 'AC3'},
            {'value': 'ape', 'label': 'APE'},
            {'value': 'caf', 'label': 'CAF'},
        ]
        context['bitrate_options'] = [
            {'value': '64k', 'label': '64 kbps'},
            {'value': '128k', 'label': '128 kbps'},
            {'value': '192k', 'label': '192 kbps'},
            {'value': '256k', 'label': '256 kbps'},
            {'value': '320k', 'label': '320 kbps'},
        ]
        return context


class AudioTrimPageView(TemplateView):
    """Audio trimming page."""
    template_name = 'audio/trim.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Audio Trimmer'
        context['input_formats'] = settings.SUPPORTED_AUDIO_FORMATS
        return context


class VideoToAudioPageView(TemplateView):
    """Video to audio extraction page."""
    template_name = 'audio/extract.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Video to Audio'
        context['input_formats'] = settings.SUPPORTED_VIDEO_FORMATS
        context['output_formats'] = [
            {'value': 'mp3', 'label': 'MP3'},
            {'value': 'wav', 'label': 'WAV'},
            {'value': 'aac', 'label': 'AAC'},
            {'value': 'm4a', 'label': 'M4A'},
            {'value': 'flac', 'label': 'FLAC'},
            {'value': 'ogg', 'label': 'OGG'},
            {'value': 'opus', 'label': 'OPUS'},
        ]
        return context
