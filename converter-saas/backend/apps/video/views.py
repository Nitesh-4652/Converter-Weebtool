"""
Video Module Views.
Video conversion and trimming API endpoints.
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
    VideoConvertSerializer,
    VideoTrimSerializer,
    ConversionJobSerializer,
)
from apps.core.utils import (
    convert_video,
    trim_video,
    get_duration,
    get_file_extension,
    generate_output_filename,
    get_file_size,
    FFmpegError,
)
from .tasks import convert_video_task, trim_video_task



class VideoConvertView(BaseConversionView):
    """
    Convert video files between formats.
    
    Supported formats:
    MP4, MKV, AVI, MOV, WEBM, FLV, WMV, 3GP, MPG, MPEG, TS, M4V, OGV, F4V, VOB, RM, RMVB
    """
    
    tool_type = ToolType.VIDEO
    operation_type = OperationType.CONVERT
    tool_name = 'video_convert'
    
    def post(self, request):
        """Convert video file to specified format."""
        
        # Check rate limit
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # Validate input
        serializer = VideoConvertSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        
        # Get validated data
        uploaded_file = serializer.validated_data['file']
        output_format = serializer.validated_data['output_format']
        
        # Build options
        options = {}
        if serializer.validated_data.get('resolution'):
            options['resolution'] = serializer.validated_data['resolution']
        if serializer.validated_data.get('video_bitrate'):
            options['video_bitrate'] = serializer.validated_data['video_bitrate']
        if serializer.validated_data.get('audio_bitrate'):
            options['audio_bitrate'] = serializer.validated_data['audio_bitrate']
        
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
            convert_video_task.delay(job.id, output_format, options)
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
            output_dir = settings.OUTPUT_DIR / 'video'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Convert video
            convert_video(input_path, output_path, output_format, options)
            
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


class VideoTrimView(BaseConversionView):
    """
    Trim video files with timeline support.
    
    Features:
    - Start and end time selection
    - Copy mode (fast, no re-encoding) or re-encode mode
    - Optional output format change
    """
    
    tool_type = ToolType.VIDEO
    operation_type = OperationType.TRIM
    tool_name = 'video_trim'
    
    def post(self, request):
        """Trim video file between start and end times."""
        
        # Check rate limit
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # Validate input
        serializer = VideoTrimSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        
        # Get validated data
        uploaded_file = serializer.validated_data['file']
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
            trim_video_task.delay(job.id, trim_start, trim_end, copy_mode, output_format)
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
            output_dir = settings.OUTPUT_DIR / 'video'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Trim video
            trim_video(input_path, output_path, trim_start, trim_end, copy_mode)
            
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


class VideoInfoView(APIView):
    """Get video file information."""
    
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Get video file metadata."""
        from apps.core.utils import get_media_info
        
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
            video_stream = None
            audio_stream = None
            
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video' and not video_stream:
                    video_stream = stream
                elif stream.get('codec_type') == 'audio' and not audio_stream:
                    audio_stream = stream
            
            response_data = {
                'filename': uploaded_file.name,
                'file_size': uploaded_file.size,
                'format': format_info.get('format_name'),
                'duration': float(format_info.get('duration', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
            }
            
            if video_stream:
                response_data['video'] = {
                    'codec': video_stream.get('codec_name'),
                    'width': video_stream.get('width'),
                    'height': video_stream.get('height'),
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')) if '/' in str(video_stream.get('r_frame_rate', '0')) else 0,
                }
            
            if audio_stream:
                response_data['audio'] = {
                    'codec': audio_stream.get('codec_name'),
                    'sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'channels': audio_stream.get('channels'),
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
