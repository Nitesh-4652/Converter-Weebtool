"""
Audio Module Views.
Audio conversion, trimming, and extraction API endpoints.
"""

import os
import time
from pathlib import Path

from django.conf import settings
from django.core.files import File
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

from apps.core.models import ConversionJob, ConvertedFile, ToolType, OperationType
from apps.core.views import BaseConversionView
from apps.core.serializers import (
    AudioConvertSerializer,
    AudioTrimSerializer,
    VideoToAudioSerializer,
    ConversionJobSerializer,
)
from apps.core.utils import (
    convert_audio,
    trim_audio,
    extract_audio_from_video,
    get_duration,
    get_file_extension,
    generate_output_filename,
    get_file_size,
    FFmpegError,
)
from .tasks import convert_audio_task, trim_audio_task, video_to_audio_task



class AudioConvertView(BaseConversionView):
    """
    Convert audio files between formats.
    
    Supported formats:
    MP3, WAV, AAC, M4A, FLAC, OGG, OPUS, AIFF, ALAC, WMA, AMR, AC3, PCM, APE, CAF
    """
    
    tool_type = ToolType.AUDIO
    operation_type = OperationType.CONVERT
    tool_name = 'audio_convert'
    
    def post(self, request):
        """Convert audio file to specified format."""
        
        # Check rate limit
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # Validate input
        serializer = AudioConvertSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        
        # Get validated data
        uploaded_file = serializer.validated_data['file']
        output_format = serializer.validated_data['output_format']
        
        # 🛡️ HARDENING: File Size Validation
        size_response = self.validate_file_size(uploaded_file)
        if size_response:
            return size_response
            
        # 🛡️ HARDENING: Duplicate Job Prevention
        duplicate_response = self.check_duplicate_job(request, uploaded_file)
        if duplicate_response:
            return duplicate_response
        
        # Build options
        options = {}
        if serializer.validated_data.get('bitrate'):
            options['bitrate'] = serializer.validated_data['bitrate']
        if serializer.validated_data.get('sample_rate'):
            options['sample_rate'] = serializer.validated_data['sample_rate']
        if serializer.validated_data.get('channels'):
            options['channels'] = serializer.validated_data['channels']
        
        # Get input format
        input_format = get_file_extension(uploaded_file.name)
        
        # Create job
        job = self.create_job(
            request=request,
            input_file=uploaded_file,
            input_format=input_format,
            output_format=output_format,
            options=options
        )
        
        # Async mode dispatch
        if settings.USE_ASYNC_CONVERSION:
            convert_audio_task.delay(job.id, output_format, options)
            self.log_usage(request, success=True, job=job)
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        try:
            # Mark as processing
            job.mark_processing()
            
            # Get input path
            input_path = job.input_file.path
            
            # Get duration
            job.duration = get_duration(input_path)
            job.save(update_fields=['duration'])
            
            # Generate output filename and path
            output_filename = generate_output_filename(uploaded_file.name, output_format)
            output_dir = settings.OUTPUT_DIR / 'audio'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Convert audio
            convert_audio(input_path, output_path, output_format, options)
            
            # Save output file to job
            with open(output_path, 'rb') as f:
                job.output_file.save(output_filename, File(f), save=False)
            
            job.mark_completed(job.output_file.name)
            
            # Create ConvertedFile record
            converted_file = ConvertedFile.objects.create(
                conversion_job=job,
                output_file=job.output_file,
                output_format=output_format,
                file_size=get_file_size(output_path)
            )
            
            # Clean up temp output file
            if os.path.exists(output_path):
                os.remove(output_path)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            # Return response
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except FFmpegError as e:
            job.mark_failed(str(e))
            self.log_usage(request, success=False, job=job)
            return Response(
                {'error': 'Conversion failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        except Exception as e:
            job.mark_failed(str(e))
            self.log_usage(request, success=False, job=job)
            return Response(
                {'error': 'An unexpected error occurred', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AudioTrimView(BaseConversionView):
    """
    Trim audio files with timeline support.
    
    Features:
    - Start and end time selection
    - Copy mode (fast, no re-encoding) or re-encode mode
    - Optional output format change
    """
    
    tool_type = ToolType.AUDIO
    operation_type = OperationType.TRIM
    tool_name = 'audio_trim'
    
    def post(self, request):
        """Trim audio file between start and end times."""
        
        # Check rate limit
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # Validate input
        serializer = AudioTrimSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        
        # Get validated data
        uploaded_file = serializer.validated_data['file']
        
        # 🛡️ HARDENING: File Size Validation
        size_response = self.validate_file_size(uploaded_file)
        if size_response:
            return size_response
            
        # 🛡️ HARDENING: Duplicate Job Prevention
        duplicate_response = self.check_duplicate_job(request, uploaded_file)
        if duplicate_response:
            return duplicate_response
            
        trim_start = serializer.validated_data['start_time']
        trim_end = serializer.validated_data['end_time']
        copy_mode = serializer.validated_data.get('copy_mode', True)
        
        # Get format
        input_format = get_file_extension(uploaded_file.name)
        output_format = serializer.validated_data.get('output_format') or input_format
        
        # Build options
        options = {
            'start_time': trim_start,
            'end_time': trim_end,
            'copy_mode': copy_mode
        }
        
        # Create job
        job = self.create_job(
            request=request,
            input_file=uploaded_file,
            input_format=input_format,
            output_format=output_format,
            options=options
        )
        
        # Async mode dispatch
        if settings.USE_ASYNC_CONVERSION:
            trim_audio_task.delay(job.id, trim_start, trim_end, copy_mode, output_format)
            self.log_usage(request, success=True, job=job)
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        try:
            # Mark as processing
            job.mark_processing()
            
            # Get input path
            input_path = job.input_file.path
            
            # Get duration and validate times
            duration = get_duration(input_path)
            if duration:
                job.duration = duration
                job.save(update_fields=['duration'])
                
                if trim_end > duration:
                    job.mark_failed(f'End time ({trim_end}s) exceeds file duration ({duration}s)')
                    return Response(
                        {'error': f'End time exceeds file duration ({duration}s)'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Generate output filename and path
            output_filename = generate_output_filename(
                uploaded_file.name,
                output_format if output_format else input_format
            )
            output_dir = settings.OUTPUT_DIR / 'audio'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Trim audio
            trim_audio(input_path, output_path, trim_start, trim_end, copy_mode)
            
            # Save output file to job
            with open(output_path, 'rb') as f:
                job.output_file.save(output_filename, File(f), save=False)
            
            job.mark_completed(job.output_file.name)
            
            # Create ConvertedFile record
            ConvertedFile.objects.create(
                conversion_job=job,
                output_file=job.output_file,
                output_format=output_format if output_format else input_format,
                file_size=get_file_size(output_path)
            )
            
            # Clean up temp output file
            if os.path.exists(output_path):
                os.remove(output_path)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            # Return response
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except FFmpegError as e:
            job.mark_failed(str(e))
            self.log_usage(request, success=False, job=job)
            return Response(
                {'error': 'Trimming failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        except Exception as e:
            job.mark_failed(str(e))
            self.log_usage(request, success=False, job=job)
            return Response(
                {'error': 'An unexpected error occurred', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VideoToAudioView(BaseConversionView):
    """
    Extract audio from video files.
    
    Supported input formats:
    MP4, MKV, WEBM, MOV, AVI, FLV, WMV, 3GP, MPG, MPEG, TS, M4V, OGV, VOB, RM, RMVB
    
    Supported output formats:
    MP3, WAV, AAC, M4A, FLAC, OGG, OPUS
    """
    
    tool_type = ToolType.AUDIO
    operation_type = OperationType.EXTRACT
    tool_name = 'video_to_audio'
    
    def post(self, request):
        """Extract audio from video file."""
        
        # Check rate limit
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # Validate input
        serializer = VideoToAudioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        
        # Get validated data
        uploaded_file = serializer.validated_data['file']
        output_format = serializer.validated_data['output_format']
        
        # 🛡️ HARDENING: File Size Validation
        size_response = self.validate_file_size(uploaded_file)
        if size_response:
            return size_response
            
        # 🛡️ HARDENING: Duplicate Job Prevention
        duplicate_response = self.check_duplicate_job(request, uploaded_file)
        if duplicate_response:
            return duplicate_response
        
        # Build options
        options = {}
        if serializer.validated_data.get('bitrate'):
            options['bitrate'] = serializer.validated_data['bitrate']
        
        # Get input format
        input_format = get_file_extension(uploaded_file.name)
        
        # Validate input is a video format
        video_formats = getattr(settings, 'SUPPORTED_VIDEO_FORMATS', [])
        if input_format not in video_formats:
            return Response(
                {'error': f'Unsupported video format: {input_format}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create job
        job = self.create_job(
            request=request,
            input_file=uploaded_file,
            input_format=input_format,
            output_format=output_format,
            options=options
        )
        
        # Async mode dispatch
        if settings.USE_ASYNC_CONVERSION:
            video_to_audio_task.delay(job.id, output_format, options)
            self.log_usage(request, success=True, job=job)
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        try:
            # Mark as processing
            job.mark_processing()
            
            # Get input path
            input_path = job.input_file.path
            
            # Get duration
            job.duration = get_duration(input_path)
            job.save(update_fields=['duration'])
            
            # Generate output filename and path
            output_filename = generate_output_filename(uploaded_file.name, output_format)
            output_dir = settings.OUTPUT_DIR / 'audio'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Extract audio
            extract_audio_from_video(input_path, output_path, output_format, options)
            
            # Save output file to job
            with open(output_path, 'rb') as f:
                job.output_file.save(output_filename, File(f), save=False)
            
            job.mark_completed(job.output_file.name)
            
            # Create ConvertedFile record
            ConvertedFile.objects.create(
                conversion_job=job,
                output_file=job.output_file,
                output_format=output_format,
                file_size=get_file_size(output_path)
            )
            
            # Clean up temp output file
            if os.path.exists(output_path):
                os.remove(output_path)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            # Return response
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except FFmpegError as e:
            job.mark_failed(str(e))
            self.log_usage(request, success=False, job=job)
            return Response(
                {'error': 'Audio extraction failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        except Exception as e:
            job.mark_failed(str(e))
            self.log_usage(request, success=False, job=job)
            return Response(
                {'error': 'An unexpected error occurred', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AudioInfoView(APIView):
    """Get audio file information."""
    
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Get audio file metadata."""
        from apps.core.utils import get_media_info, get_client_ip
        
        if 'file' not in request.data:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.data['file']
        
        # Save temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        try:
            with open(temp_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            # Get media info
            info = get_media_info(temp_path)
            
            # Extract relevant data
            format_info = info.get('format', {})
            audio_stream = None
            
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_stream = stream
                    break
            
            response_data = {
                'filename': uploaded_file.name,
                'file_size': uploaded_file.size,
                'format': format_info.get('format_name'),
                'duration': float(format_info.get('duration', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
            }
            
            if audio_stream:
                response_data['audio'] = {
                    'codec': audio_stream.get('codec_name'),
                    'sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'channels': audio_stream.get('channels'),
                    'channel_layout': audio_stream.get('channel_layout'),
                }
            
            return Response(response_data)
        
        except Exception as e:
            return Response(
                {'error': f'Failed to get file info: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
