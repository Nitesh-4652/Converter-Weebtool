"""
Core Serializers for File Converter SaaS.
DRF serializers for all core models.
"""

from rest_framework import serializers
from django.conf import settings

from .models import ConversionJob, UploadedFile, ConvertedFile, ToolUsageLog


class ConversionJobSerializer(serializers.ModelSerializer):
    """Serializer for ConversionJob model."""
    
    processing_time = serializers.ReadOnlyField()
    download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ConversionJob
        fields = [
            'id', 'tool_type', 'operation_type', 'status',
            'input_format', 'output_format', 'file_size', 'duration',
            'options', 'created_at', 'completed_at',
            'error_message', 'processing_time', 'download_url'
        ]
        read_only_fields = [
            'id', 'status', 'created_at', 'completed_at',
            'error_message', 'processing_time', 'download_url'
        ]
    
    def get_download_url(self, obj):
        """Get download URL for output file."""
        if obj.output_file and obj.status == 'completed':
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.output_file.url)
            return obj.output_file.url
        return None


class ConversionJobCreateSerializer(serializers.Serializer):
    """Serializer for creating a conversion job."""
    
    file = serializers.FileField(required=True)
    output_format = serializers.CharField(max_length=20, required=True)
    options = serializers.JSONField(required=False, default=dict)
    
    def validate_file(self, value):
        """Validate uploaded file."""
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 500 * 1024 * 1024)
        
        if value.size > max_size:
            raise serializers.ValidationError(
                f'File size exceeds maximum allowed ({max_size // (1024*1024)}MB)'
            )
        
        return value
    
    def validate_output_format(self, value):
        """Validate output format."""
        return value.lower().strip()


class AudioConvertSerializer(serializers.Serializer):
    """Serializer for audio conversion requests."""
    
    file = serializers.FileField(required=True)
    output_format = serializers.ChoiceField(
        choices=[
            ('mp3', 'MP3'), ('wav', 'WAV'), ('aac', 'AAC'), ('m4a', 'M4A'),
            ('flac', 'FLAC'), ('ogg', 'OGG'), ('opus', 'OPUS'),
            ('aiff', 'AIFF'), ('wma', 'WMA'), ('amr', 'AMR'),
            ('ac3', 'AC3'), ('ape', 'APE'), ('caf', 'CAF'),
        ],
        required=True
    )
    bitrate = serializers.CharField(required=False, allow_blank=True)
    sample_rate = serializers.IntegerField(required=False, min_value=8000, max_value=192000)
    channels = serializers.IntegerField(required=False, min_value=1, max_value=8)


class AudioTrimSerializer(serializers.Serializer):
    """Serializer for audio trimming requests."""
    
    file = serializers.FileField(required=True)
    start_time = serializers.FloatField(required=True, min_value=0)
    end_time = serializers.FloatField(required=True, min_value=0)
    copy_mode = serializers.BooleanField(default=True)
    output_format = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate start and end times."""
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError({
                'end_time': 'End time must be greater than start time.'
            })
        return data


class VideoToAudioSerializer(serializers.Serializer):
    """Serializer for extracting audio from video."""
    
    file = serializers.FileField(required=True)
    output_format = serializers.ChoiceField(
        choices=[
            ('mp3', 'MP3'), ('wav', 'WAV'), ('aac', 'AAC'), ('m4a', 'M4A'),
            ('flac', 'FLAC'), ('ogg', 'OGG'), ('opus', 'OPUS'),
        ],
        required=True
    )
    bitrate = serializers.CharField(required=False, allow_blank=True)


class VideoConvertSerializer(serializers.Serializer):
    """Serializer for video conversion requests."""
    
    file = serializers.FileField(required=True)
    output_format = serializers.ChoiceField(
        choices=[
            ('mp4', 'MP4'), ('mkv', 'MKV'), ('avi', 'AVI'), ('mov', 'MOV'),
            ('webm', 'WEBM'), ('flv', 'FLV'), ('wmv', 'WMV'),
            ('3gp', '3GP'), ('mpg', 'MPG'), ('mpeg', 'MPEG'),
            ('ts', 'TS'), ('m4v', 'M4V'), ('ogv', 'OGV'),
        ],
        required=True
    )
    resolution = serializers.CharField(required=False, allow_blank=True)
    video_bitrate = serializers.CharField(required=False, allow_blank=True)
    audio_bitrate = serializers.CharField(required=False, allow_blank=True)


class VideoTrimSerializer(serializers.Serializer):
    """Serializer for video trimming requests."""
    
    file = serializers.FileField(required=True)
    start_time = serializers.FloatField(required=True, min_value=0)
    end_time = serializers.FloatField(required=True, min_value=0)
    copy_mode = serializers.BooleanField(default=True)
    output_format = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate start and end times."""
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError({
                'end_time': 'End time must be greater than start time.'
            })
        return data


class UploadedFileSerializer(serializers.ModelSerializer):
    """Serializer for UploadedFile model."""
    
    class Meta:
        model = UploadedFile
        fields = [
            'id', 'original_name', 'file_type', 'file_size',
            'metadata', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']


class ConvertedFileSerializer(serializers.ModelSerializer):
    """Serializer for ConvertedFile model."""
    
    download_url = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = ConvertedFile
        fields = [
            'id', 'conversion_job', 'output_format', 'file_size',
            'created_at', 'expires_at', 'download_count',
            'download_url', 'is_expired'
        ]
        read_only_fields = ['id', 'created_at', 'download_count']
    
    def get_download_url(self, obj):
        """Get download URL for output file."""
        if obj.output_file and not obj.is_expired:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.output_file.url)
            return obj.output_file.url
        return None


class ToolUsageLogSerializer(serializers.ModelSerializer):
    """Serializer for ToolUsageLog model."""
    
    class Meta:
        model = ToolUsageLog
        fields = [
            'id', 'tool_name', 'used_at', 'success', 'processing_time_ms'
        ]
        read_only_fields = ['id', 'used_at']


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check response."""
    
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    version = serializers.CharField()
    database = serializers.CharField()
    ffmpeg = serializers.CharField()
