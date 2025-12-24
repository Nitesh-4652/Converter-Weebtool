"""
Core Views for File Converter SaaS.
Home page, health check, and base API views.
"""

import subprocess
from datetime import timedelta
from django.views.generic import TemplateView
from django.utils import timezone
from django.db import connection

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import ConversionJob, ConvertedFile
from .serializers import ConversionJobSerializer, HealthCheckSerializer
from .utils import get_ffmpeg_path


class HomeView(TemplateView):
    """Home page view."""
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'File Converter SaaS'
        context['tools'] = [
            {
                'name': 'Audio Converter',
                'description': 'Convert audio files between 15+ formats',
                'url': '/audio/',
                'icon': '🎵'
            },
            {
                'name': 'Video Converter',
                'description': 'Convert video files between 17+ formats',
                'url': '/video/',
                'icon': '🎬'
            },
            {
                'name': 'Image Converter',
                'description': 'Convert images between 17+ formats',
                'url': '/image/',
                'icon': '🖼️'
            },
            {
                'name': 'PDF Tools',
                'description': 'Convert, merge, split, and edit PDFs',
                'url': '/pdf/',
                'icon': '📄'
            },
        ]
        return context


class HealthCheckView(APIView):
    """Health check endpoint for monitoring."""
    
    def get(self, request):
        """Return system health status."""
        from django.conf import settings
        from django.db import connection
        import shutil
        import subprocess
        
        show_details = getattr(settings, 'HEALTH_CHECK_SENSITIVE_INFO', False) or settings.DEBUG
        
        # Check database connection
        db_status = 'healthy'
        db_error = None
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception as e:
            db_status = 'unhealthy'
            db_error = str(e)
            
        # Check Database Schema (Tables)
        schema_status = 'healthy'
        missing_tables = []
        required_tables = [
            'conversion_jobs', 
            'uploaded_files', 
            'converted_files',
            'tool_usage_logs'
        ]
        
        try:
            existing_tables = connection.introspection.table_names()
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                schema_status = 'unhealthy'
        except Exception as e:
            schema_status = 'unknown'
            db_error = f"{db_error} | Schema Error: {str(e)}" if db_error else f"Schema Error: {str(e)}"
        
        # Check FFmpeg
        ffmpeg_status = 'healthy'
        ffmpeg_error = None
        try:
            # Use utility if possible, or direct path
            from apps.core.utils import get_ffmpeg_path
            result = subprocess.run(
                [get_ffmpeg_path(), '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                ffmpeg_status = 'unhealthy'
                ffmpeg_error = 'FFmpeg process returned non-zero exit code'
        except Exception as e:
            ffmpeg_status = 'unhealthy'
            ffmpeg_error = str(e)
            
        # Check Storage (Disk space)
        storage_status = 'healthy'
        storage_info = {}
        try:
            total, used, free = shutil.disk_usage(settings.MEDIA_ROOT)
            free_gb = free / (2**30)
            if free_gb < 0.5:  # Less than 500MB free
                storage_status = 'warning'
            storage_info = {
                'free_gb': round(free_gb, 2),
                'total_gb': round(total / (2**30), 2),
                'used_percent': round((used / total) * 100, 1)
            }
        except Exception as e:
            storage_status = 'unknown'
            storage_info = {'error': str(e)}
        
        # Overall status
        is_healthy = (
            db_status == 'healthy' and 
            schema_status == 'healthy' and 
            ffmpeg_status == 'healthy' and 
            storage_status != 'unhealthy'
        )
        
        data = {
            'status': 'healthy' if is_healthy else 'degraded',
            'timestamp': timezone.now(),
            'version': '1.0.2',
        }
        
        # Add details based on privacy settings
        if show_details:
            data.update({
                'database': db_status,
                'schema': schema_status,
                'ffmpeg': ffmpeg_status,
                'storage': storage_status,
                'details': {
                    'db_error': db_error,
                    'ffmpeg_error': ffmpeg_error,
                    'missing_tables': missing_tables if missing_tables else None,
                    'storage_info': storage_info
                }
            })
        else:
            data['checks'] = {
                'database': db_status == 'healthy',
                'schema': schema_status == 'healthy',
                'ffmpeg': ffmpeg_status == 'healthy',
                'storage': storage_status != 'unhealthy'
            }
        
        serializer = HealthCheckSerializer(data)
        return Response(serializer.data)


class ConversionJobListView(APIView):
    """List recent conversion jobs."""
    
    def get(self, request):
        """Get recent conversion jobs for client IP."""
        from .utils import get_client_ip
        
        client_ip = get_client_ip(request)
        jobs = ConversionJob.objects.filter(
            client_ip=client_ip
        ).order_by('-created_at')[:20]
        
        serializer = ConversionJobSerializer(
            jobs, many=True, context={'request': request}
        )
        return Response(serializer.data)


class ConversionJobDetailView(APIView):
    """Get conversion job details."""
    
    def get(self, request, job_id):
        """Get job details by ID."""
        try:
            job = ConversionJob.objects.get(id=job_id)
            serializer = ConversionJobSerializer(job, context={'request': request})
            return Response(serializer.data)
        except ConversionJob.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DownloadFileView(APIView):
    """Download converted file."""
    
    def get(self, request, file_id):
        """Download file by ID."""
        from django.http import FileResponse
        import os
        
        try:
            converted_file = ConvertedFile.objects.get(id=file_id)
            
            if converted_file.is_expired:
                return Response(
                    {'error': 'File has expired'},
                    status=status.HTTP_410_GONE
                )
            
            # Get file path and clean filename
            file_path = converted_file.output_file.path
            
            # Use original_filename if set, otherwise extract from file path
            file_name = converted_file.original_filename or converted_file.output_file.name.split('/')[-1]
            
            if not os.path.exists(file_path):
                return Response(
                    {'error': 'File not found on server'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Use FileResponse for efficient streaming
            # This is cloud-safe and memory-efficient
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=file_name
            )
            
            # Increment download count
            converted_file.record_download()
            
            return response
            
        except ConvertedFile.DoesNotExist:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class BaseConversionView(APIView):
    """Base class for conversion views."""
    
    parser_classes = [MultiPartParser, FormParser]
    
    tool_type = None
    operation_type = None
    tool_name = None
    
    def get_client_info(self, request):
        """Get client IP and user agent."""
        from .utils import get_client_ip, get_user_agent
        return {
            'client_ip': get_client_ip(request),
            'user_agent': get_user_agent(request)
        }
    
    def check_rate_limit(self, request):
        """Check rate limit for client."""
        from .utils import check_rate_limit, get_client_ip
        
        client_ip = get_client_ip(request)
        is_allowed, remaining = check_rate_limit(client_ip)
        
        if not is_allowed:
            return Response(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'remaining_requests': remaining
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return None
        
    def validate_file_size(self, input_file):
        """Validate file size against settings."""
        from django.conf import settings
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 500 * 1024 * 1024)
        
        if input_file.size > max_size:
            return Response(
                {
                    'error': f'File too large. Maximum allowed size is {max_size / (1024*1024)}MB.',
                    'file_size': input_file.size,
                    'max_size': max_size
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )
        return None

    def check_duplicate_job(self, request, input_file):
        """
        Check if an identical job is already processing for this IP.
        Prevents accidental double-clicks from spawning multiple tasks.
        """
        from .utils import get_client_ip
        from .models import ConversionJob, JobStatus
        
        client_ip = get_client_ip(request)
        
        # Look for jobs with same IP, same tool, same size, and PENDING/PROCESSING status
        # within the last 5 minutes
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        
        duplicate = ConversionJob.objects.filter(
            client_ip=client_ip,
            tool_type=self.tool_type,
            file_size=input_file.size,
            status__in=[JobStatus.PENDING, JobStatus.PROCESSING],
            created_at__gte=five_minutes_ago
        ).first()
        
        if duplicate:
            return Response(
                {
                    'error': 'A similar job is already being processed. Please wait.',
                    'job_id': str(duplicate.id)
                },
                status=status.HTTP_409_CONFLICT
            )
        return None
    
    def create_job(self, request, input_file, input_format, output_format, options=None):
        """Create a conversion job."""
        client_info = self.get_client_info(request)
        
        job = ConversionJob.objects.create(
            tool_type=self.tool_type,
            operation_type=self.operation_type,
            input_file=input_file,
            input_format=input_format,
            output_format=output_format,
            file_size=input_file.size,
            options=options or {},
            **client_info
        )
        
        return job
    
    def log_usage(self, request, success=True, job=None, processing_time_ms=None):
        """Log tool usage."""
        from .utils import log_tool_usage, get_client_ip, get_user_agent
        
        log_tool_usage(
            tool_name=self.tool_name,
            client_ip=get_client_ip(request),
            success=success,
            conversion_job=job,
            processing_time_ms=processing_time_ms,
            user_agent=get_user_agent(request)
        )
