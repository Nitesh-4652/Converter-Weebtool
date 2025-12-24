"""
Image Module Views.
Image conversion API endpoints using Pillow.
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
from rest_framework import serializers

from apps.core.models import ConversionJob, ConvertedFile, ToolType, OperationType
from apps.core.views import BaseConversionView
from apps.core.serializers import ConversionJobSerializer
from apps.core.utils import (
    get_file_extension,
    generate_output_filename,
    get_file_size,
)
from .utils import (
    convert_image,
    convert_svg_to_image,
    convert_heic_to_image,
    get_image_info,
    ImageConversionError,
)
from .tasks import convert_image_task



class ImageConvertSerializer(serializers.Serializer):
    """Serializer for image conversion requests."""
    
    file = serializers.FileField(required=True)
    output_format = serializers.ChoiceField(
        choices=[
            ('jpg', 'JPEG'), ('png', 'PNG'), ('webp', 'WEBP'),
            ('gif', 'GIF'), ('bmp', 'BMP'), ('tiff', 'TIFF'),
            ('ico', 'ICO'), ('ppm', 'PPM'),
        ],
        required=True
    )
    quality = serializers.IntegerField(required=False, min_value=1, max_value=100, default=85)
    width = serializers.IntegerField(required=False, min_value=1, max_value=10000)
    height = serializers.IntegerField(required=False, min_value=1, max_value=10000)


class ImageConvertView(BaseConversionView):
    """
    Convert images between formats.
    
    Supported formats:
    JPG, PNG, WEBP, GIF, SVG, BMP, TIFF, ICO, HEIC, AVIF, PPM, PGM
    """
    
    tool_type = ToolType.IMAGE
    operation_type = OperationType.CONVERT
    tool_name = 'image_convert'
    
    def post(self, request):
        """Convert image file to specified format."""
        
        # Check rate limit
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        # Validate input
        serializer = ImageConvertSerializer(data=request.data)
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
        options = {'quality': serializer.validated_data.get('quality', 85)}
        if serializer.validated_data.get('width'):
            options['width'] = serializer.validated_data['width']
        if serializer.validated_data.get('height'):
            options['height'] = serializer.validated_data['height']
        
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
            convert_image_task.delay(job.id, output_format, options)
            self.log_usage(request, success=True, job=job)
            response_serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        try:
            # Mark as processing
            job.mark_processing()
            
            # Get input path
            input_path = job.input_file.path
            
            # Generate output filename and path
            output_filename = generate_output_filename(uploaded_file.name, output_format)
            output_dir = settings.OUTPUT_DIR / 'image'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Convert based on input format
            if input_format.lower() == 'svg':
                convert_svg_to_image(input_path, output_path, output_format, options)
            elif input_format.lower() in ['heic', 'heif']:
                convert_heic_to_image(input_path, output_path, output_format, options)
            else:
                convert_image(input_path, output_path, output_format, options)
            
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
        
        except ImageConversionError as e:
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


class ImageInfoView(APIView):
    """Get image file information."""
    
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Get image file metadata."""
        
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
            
            # Get image info
            info = get_image_info(temp_path)
            info['filename'] = uploaded_file.name
            info['file_size'] = uploaded_file.size
            
            return Response(info)
        
        except Exception as e:
            return Response(
                {'error': f'Failed to get file info: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
