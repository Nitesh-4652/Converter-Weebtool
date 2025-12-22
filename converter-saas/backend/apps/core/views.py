"""
Core Views for File Converter SaaS.
Home page, health check, and base API views.
"""

import subprocess
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
        
        # Check database
        db_status = 'healthy'
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        # Check FFmpeg
        ffmpeg_status = 'healthy'
        try:
            result = subprocess.run(
                [get_ffmpeg_path(), '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                ffmpeg_status = 'unhealthy: FFmpeg not working'
        except FileNotFoundError:
            ffmpeg_status = 'unhealthy: FFmpeg not found'
        except Exception as e:
            ffmpeg_status = f'unhealthy: {str(e)}'
        
        data = {
            'status': 'healthy' if db_status == 'healthy' and ffmpeg_status == 'healthy' else 'degraded',
            'timestamp': timezone.now(),
            'version': '1.0.0',
            'database': db_status,
            'ffmpeg': ffmpeg_status, 
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
        
        try:
            converted_file = ConvertedFile.objects.get(id=file_id)
            
            if converted_file.is_expired:
                return Response(
                    {'error': 'File has expired'},
                    status=status.HTTP_410_GONE
                )
            
            # Record download
            converted_file.record_download()
            
            # Return file
            response = FileResponse(
                converted_file.output_file.open('rb'),
                as_attachment=True,
                filename=converted_file.output_file.name.split('/')[-1]
            )
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
