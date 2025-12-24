"""
PDF Module Views.
PDF conversion and manipulation API endpoints.
"""

import os
import time
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.http import FileResponse
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
    get_client_ip,
    get_user_agent,
    log_tool_usage,
)
from .utils import (
    merge_pdfs,
    split_pdf,
    compress_pdf,
    rotate_pdf,
    delete_pages,
    reorder_pages,
    protect_pdf,
    unlock_pdf,
    images_to_pdf,
    pdf_to_images,
    get_pdf_info,
    PDFError,
)
from .tasks import (
    convert_to_pdf_task,
    merge_pdfs_task,
    split_pdf_task,
    compress_pdf_task,
    rotate_pdf_task,
    protect_pdf_task,
    unlock_pdf_task,
    images_to_pdf_task,
    pdf_to_images_task,
)



# ============================================
# SERIALIZERS
# ============================================

class PDFMergeSerializer(serializers.Serializer):
    """Serializer for PDF merge requests."""
    files = serializers.ListField(
        child=serializers.FileField(),
        min_length=2,
        max_length=50
    )


class PDFSplitSerializer(serializers.Serializer):
    """Serializer for PDF split requests."""
    file = serializers.FileField(required=True)
    page_ranges = serializers.CharField(
        required=False,
        help_text='Page ranges like "1-3,5-7" or leave empty for individual pages'
    )


class PDFCompressSerializer(serializers.Serializer):
    """Serializer for PDF compress requests."""
    file = serializers.FileField(required=True)
    quality = serializers.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='medium'
    )


class PDFRotateSerializer(serializers.Serializer):
    """Serializer for PDF rotate requests."""
    file = serializers.FileField(required=True)
    rotation = serializers.ChoiceField(
        choices=[(90, '90°'), (180, '180°'), (270, '270°')],
        required=True
    )
    pages = serializers.CharField(
        required=False,
        help_text='Page numbers like "1,3,5" or leave empty for all pages'
    )


class PDFDeletePagesSerializer(serializers.Serializer):
    """Serializer for PDF delete pages requests."""
    file = serializers.FileField(required=True)
    pages = serializers.CharField(
        required=True,
        help_text='Page numbers to delete like "1,3,5"'
    )


class PDFReorderSerializer(serializers.Serializer):
    """Serializer for PDF reorder requests."""
    file = serializers.FileField(required=True)
    order = serializers.CharField(
        required=True,
        help_text='New page order like "3,1,2,4"'
    )


class PDFProtectSerializer(serializers.Serializer):
    """Serializer for PDF protect requests."""
    file = serializers.FileField(required=True)
    password = serializers.CharField(required=True, min_length=4)
    owner_password = serializers.CharField(required=False, min_length=4)


class PDFUnlockSerializer(serializers.Serializer):
    """Serializer for PDF unlock requests."""
    file = serializers.FileField(required=True)
    password = serializers.CharField(required=True)


class ImagesToPDFSerializer(serializers.Serializer):
    """Serializer for images to PDF requests."""
    files = serializers.ListField(
        child=serializers.FileField(),
        min_length=1,
        max_length=100
    )
    page_size = serializers.ChoiceField(
        choices=[('A4', 'A4'), ('Letter', 'Letter')],
        default='A4'
    )


class PDFToImagesSerializer(serializers.Serializer):
    """Serializer for PDF to images requests."""
    file = serializers.FileField(required=True)
    output_format = serializers.ChoiceField(
        choices=[('png', 'PNG'), ('jpg', 'JPEG')],
        default='png'
    )
    dpi = serializers.IntegerField(default=200, min_value=72, max_value=600)


# ============================================
# VIEWS
# ============================================

class PDFMergeView(BaseConversionView):
    """Merge multiple PDFs into one."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.MERGE
    tool_name = 'pdf_merge'
    
    def post(self, request):
        """Merge PDF files."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFMergeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        files = serializer.validated_data['files']
        
        # Save files temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp' / 'merge'
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        input_paths = []
        try:
            for i, f in enumerate(files):
                temp_path = str(temp_dir / f'{i}_{f.name}')
                with open(temp_path, 'wb') as out:
                    for chunk in f.chunks():
                        out.write(chunk)
                input_paths.append(temp_path)
            
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=files[0],  # Use first file as representative
                input_format='pdf',
                output_format='pdf',
                options={'batch_size': len(files), 'input_paths': input_paths}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                merge_pdfs_task.delay(job.id, {'input_paths': input_paths, 'output_filename': output_filename})
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode (Existing logic)
            job.mark_processing()
            
            # Merge PDFs
            merge_pdfs(input_paths, output_path)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            # Return file
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Merge failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up temp files
            for path in input_paths:
                if os.path.exists(path):
                    os.remove(path)


class PDFSplitView(BaseConversionView):
    """Split PDF into multiple files."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.SPLIT
    tool_name = 'pdf_split'
    
    def post(self, request):
        """Split PDF file."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFSplitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        uploaded_file = serializer.validated_data['file']
        page_ranges_str = serializer.validated_data.get('page_ranges', '')
        
        # Parse page ranges
        page_ranges = None
        if page_ranges_str:
            try:
                page_ranges = []
                for part in page_ranges_str.split(','):
                    if '-' in part:
                        start, end = part.split('-')
                        page_ranges.append((int(start.strip()), int(end.strip())))
                    else:
                        page_num = int(part.strip())
                        page_ranges.append((page_num, page_num))
            except ValueError:
                return Response(
                    {'error': 'Invalid page ranges format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Save file temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp' / 'split'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        output_dir = settings.OUTPUT_DIR / 'pdf' / f'split_{int(time.time())}'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(temp_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=uploaded_file,
                input_format='pdf',
                output_format='zip',
                options={'page_ranges': page_ranges_str}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                split_pdf_task.delay(job.id, page_ranges)
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Split PDF
            output_paths = split_pdf(temp_path, str(output_dir), page_ranges)
            
            # Create ZIP file
            zip_filename = f'split_{int(time.time())}.zip'
            zip_path = str(settings.OUTPUT_DIR / 'pdf' / zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for path in output_paths:
                    zipf.write(path, os.path.basename(path))
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            # Return ZIP file
            response = FileResponse(
                open(zip_path, 'rb'),
                as_attachment=True,
                filename=zip_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Split failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)


class PDFCompressView(BaseConversionView):
    """Compress PDF file."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.COMPRESS
    tool_name = 'pdf_compress'
    
    def post(self, request):
        """Compress PDF file."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFCompressSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        uploaded_file = serializer.validated_data['file']
        quality = serializer.validated_data['quality']
        
        # Save file temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        output_filename = f'compressed_{uploaded_file.name}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        try:
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=uploaded_file,
                input_format='pdf',
                output_format='pdf',
                options={'quality': quality}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                compress_pdf_task.delay(job.id, quality)
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Compress PDF
            compress_pdf(temp_path, output_path, quality)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            # Return file
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Compression failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class PDFRotateView(BaseConversionView):
    """Rotate PDF pages."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.ROTATE
    tool_name = 'pdf_rotate'
    
    def post(self, request):
        """Rotate PDF pages."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFRotateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        uploaded_file = serializer.validated_data['file']
        rotation = int(serializer.validated_data['rotation'])
        pages_str = serializer.validated_data.get('pages', '')
        
        # Parse pages
        pages = None
        if pages_str:
            try:
                pages = [int(p.strip()) for p in pages_str.split(',')]
            except ValueError:
                return Response(
                    {'error': 'Invalid pages format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Save file temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        output_filename = f'rotated_{uploaded_file.name}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        try:
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=uploaded_file,
                input_format='pdf',
                output_format='pdf',
                options={'rotation': rotation, 'pages': pages}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                rotate_pdf_task.delay(job.id, rotation, pages)
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Rotate PDF
            rotate_pdf(temp_path, output_path, rotation, pages)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Rotation failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class PDFProtectView(BaseConversionView):
    """Add password protection to PDF."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.PROTECT
    tool_name = 'pdf_protect'
    
    def post(self, request):
        """Protect PDF with password."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFProtectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        uploaded_file = serializer.validated_data['file']
        password = serializer.validated_data['password']
        owner_password = serializer.validated_data.get('owner_password')
        
        # Save file temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        output_filename = f'protected_{uploaded_file.name}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        try:
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=uploaded_file,
                input_format='pdf',
                output_format='pdf',
                options={'password': password, 'owner_password': owner_password}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                protect_pdf_task.delay(job.id, password, owner_password)
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Protect PDF
            protect_pdf(temp_path, output_path, password, owner_password)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Protection failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class PDFUnlockView(BaseConversionView):
    """Remove password protection from PDF."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.UNLOCK
    tool_name = 'pdf_unlock'
    
    def post(self, request):
        """Unlock protected PDF."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFUnlockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        uploaded_file = serializer.validated_data['file']
        password = serializer.validated_data['password']
        
        # Save file temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        output_filename = f'unlocked_{uploaded_file.name}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        try:
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=uploaded_file,
                input_format='pdf',
                output_format='pdf',
                options={'password': password}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                unlock_pdf_task.delay(job.id, password)
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Unlock PDF
            unlock_pdf(temp_path, output_path, password)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Unlock failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class ImagesToPDFView(BaseConversionView):
    """Convert images to PDF."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.CONVERT
    tool_name = 'images_to_pdf'
    
    def post(self, request):
        """Convert images to PDF."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = ImagesToPDFSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        files = serializer.validated_data['files']
        page_size = serializer.validated_data['page_size']
        
        # Save files temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp' / 'img2pdf'
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        input_paths = []
        try:
            for i, f in enumerate(files):
                temp_path = str(temp_dir / f'{i}_{f.name}')
                with open(temp_path, 'wb') as out:
                    for chunk in f.chunks():
                        out.write(chunk)
                input_paths.append(temp_path)
            
            # Generate output
            output_filename = f'images_{int(time.time())}.pdf'
            output_dir = settings.OUTPUT_DIR / 'pdf'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / output_filename)
            
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=files[0],  # Use first image as representative
                input_format='image',
                output_format='pdf',
                options={'batch_size': len(files), 'input_paths': input_paths, 'page_size': page_size}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                images_to_pdf_task.delay(job.id, {'input_paths': input_paths, 'page_size': page_size})
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Convert to PDF
            images_to_pdf(input_paths, output_path, page_size)
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Conversion failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            for path in input_paths:
                if os.path.exists(path):
                    os.remove(path)


class PDFToImagesView(BaseConversionView):
    """Convert PDF to images."""
    
    tool_type = ToolType.PDF
    operation_type = OperationType.CONVERT
    tool_name = 'pdf_to_images'
    
    def post(self, request):
        """Convert PDF to images."""
        
        rate_limit_response = self.check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response
        
        serializer = PDFToImagesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        uploaded_file = serializer.validated_data['file']
        output_format = serializer.validated_data['output_format']
        dpi = serializer.validated_data['dpi']
        
        # Save file temporarily
        temp_dir = settings.UPLOAD_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / uploaded_file.name)
        
        output_dir = settings.OUTPUT_DIR / 'pdf' / f'pdf2img_{int(time.time())}'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(temp_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            # Create job for tracking
            job = self.create_job(
                request=request,
                input_file=uploaded_file,
                input_format='pdf',
                output_format='zip',
                options={'output_format': output_format, 'dpi': dpi}
            )
            
            # Async mode dispatch
            if settings.USE_ASYNC_CONVERSION:
                pdf_to_images_task.delay(job.id, output_format, dpi)
                self.log_usage(request, success=True, job=job)
                response_serializer = ConversionJobSerializer(job, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Sync mode
            job.mark_processing()
            
            # Convert to images
            output_paths = pdf_to_images(temp_path, str(output_dir), output_format, dpi)
            
            # Create ZIP file
            zip_filename = f'pdf_images_{int(time.time())}.zip'
            zip_path = str(settings.OUTPUT_DIR / 'pdf' / zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for path in output_paths:
                    zipf.write(path, os.path.basename(path))
            
            # Log usage
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.log_usage(request, success=True, job=job, processing_time_ms=processing_time_ms)
            
            response = FileResponse(
                open(zip_path, 'rb'),
                as_attachment=True,
                filename=zip_filename
            )
            return response
        
        except PDFError as e:
            return Response(
                {'error': 'Conversion failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class PDFInfoView(APIView):
    """Get PDF file information."""
    
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Get PDF file metadata."""
        
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
            
            # Get PDF info
            info = get_pdf_info(temp_path)
            info['filename'] = uploaded_file.name
            info['file_size'] = uploaded_file.size
            
            return Response(info)
        
        except Exception as e:
            return Response(
                {'error': f'Failed to get file info: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
