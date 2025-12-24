"""
Core Database Models for File Converter SaaS.
All production-ready models with proper indexes and relationships.
"""

import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta


def upload_path(instance, filename):
    """Generate upload path for files."""
    date = timezone.now().strftime('%Y/%m/%d')
    return f'uploads/{date}/{uuid.uuid4().hex[:8]}_{filename}'


def output_path(instance, filename):
    """Generate output path for converted files."""
    date = timezone.now().strftime('%Y/%m/%d')
    return f'outputs/{date}/{uuid.uuid4().hex[:8]}_{filename}'


class ToolType(models.TextChoices):
    """Tool type choices."""
    AUDIO = 'audio', 'Audio'
    VIDEO = 'video', 'Video'
    IMAGE = 'image', 'Image'
    PDF = 'pdf', 'PDF'


class OperationType(models.TextChoices):
    """Operation type choices."""
    CONVERT = 'convert', 'Convert'
    TRIM = 'trim', 'Trim'
    MERGE = 'merge', 'Merge'
    SPLIT = 'split', 'Split'
    COMPRESS = 'compress', 'Compress'
    EXTRACT = 'extract', 'Extract'
    ROTATE = 'rotate', 'Rotate'
    PROTECT = 'protect', 'Protect'
    UNLOCK = 'unlock', 'Unlock'
    REORDER = 'reorder', 'Reorder'
    DELETE_PAGES = 'delete_pages', 'Delete Pages'


class JobStatus(models.TextChoices):
    """Job status choices."""
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class ConversionJob(models.Model):
    """
    Tracks all file conversion jobs.
    Central model for all audio, video, image, and PDF operations.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Job type and operation
    tool_type = models.CharField(
        max_length=10,
        choices=ToolType.choices,
        db_index=True
    )
    operation_type = models.CharField(
        max_length=20,
        choices=OperationType.choices,
        default=OperationType.CONVERT
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        db_index=True
    )
    
    # Files
    input_file = models.FileField(
        upload_to=upload_path,
        max_length=500
    )
    output_file = models.FileField(
        upload_to=output_path,
        max_length=500,
        null=True,
        blank=True
    )
    
    # Format info
    input_format = models.CharField(max_length=20)
    output_format = models.CharField(max_length=20)
    
    # File metadata
    file_size = models.BigIntegerField(
        help_text='File size in bytes'
    )
    duration = models.FloatField(
        null=True,
        blank=True,
        help_text='Duration in seconds (for audio/video)'
    )
    
    # Additional options (JSON for flexibility)
    options = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional conversion options like start_time, end_time, quality, etc.'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    
    # Rate limiting / analytics
    client_ip = models.GenericIPAddressField(db_index=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    
    class Meta:
        db_table = 'conversion_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'tool_type']),
            models.Index(fields=['client_ip', 'created_at']),
            models.Index(fields=['tool_type', 'operation_type']),
        ]
        verbose_name = 'Conversion Job'
        verbose_name_plural = 'Conversion Jobs'
    
    def __str__(self):
        return f'{self.tool_type}:{self.operation_type} - {self.status} ({self.id})'
    
    def mark_processing(self):
        """Mark job as processing."""
        self.status = JobStatus.PROCESSING
        self.save(update_fields=['status'])
    
    def mark_completed(self, output_file_path):
        """Mark job as completed with output file."""
        self.status = JobStatus.COMPLETED
        self.output_file = output_file_path
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'output_file', 'completed_at'])
    
    def mark_failed(self, error_message):
        """Mark job as failed with error message."""
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])
    
    @property
    def processing_time(self):
        """Calculate processing time in seconds."""
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).total_seconds()
        return None


class UploadedFile(models.Model):
    """
    Stores information about uploaded files.
    Tracks original file metadata before conversion.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    original_name = models.CharField(
        max_length=500,
        help_text='Original filename from user'
    )
    stored_file = models.FileField(
        upload_to=upload_path,
        max_length=500
    )
    
    file_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text='MIME type or file extension'
    )
    file_size = models.BigIntegerField(
        help_text='File size in bytes'
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional file metadata (duration, dimensions, etc.)'
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Link to conversion job (optional)
    conversion_job = models.ForeignKey(
        ConversionJob,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='uploaded_files'
    )
    
    class Meta:
        db_table = 'uploaded_files'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['file_type', 'uploaded_at']),
        ]
        verbose_name = 'Uploaded File'
        verbose_name_plural = 'Uploaded Files'
    
    def __str__(self):
        return f'{self.original_name} ({self.file_type})'


class ConvertedFile(models.Model):
    """
    Stores converted/output files with expiry.
    Files are automatically cleaned up after expiry.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    conversion_job = models.ForeignKey(
        ConversionJob,
        on_delete=models.CASCADE,
        related_name='converted_files'
    )
    
    output_file = models.FileField(
        upload_to=output_path,
        max_length=500
    )
    output_format = models.CharField(max_length=20)
    
    # User-friendly filename (clean, no hashes)
    original_filename = models.CharField(
        max_length=500,
        help_text='Clean filename shown to user (e.g., "song.mp3")',
        blank=True,
        default=''
    )
    
    file_size = models.BigIntegerField(
        help_text='Output file size in bytes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    
    # Download tracking
    download_count = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'converted_files'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['expires_at']),
            models.Index(fields=['conversion_job', 'created_at']),
        ]
        verbose_name = 'Converted File'
        verbose_name_plural = 'Converted Files'
    
    def __str__(self):
        return f'{self.output_format} - {self.conversion_job_id}'
    
    def save(self, *args, **kwargs):
        """Set expiry date if not provided."""
        if not self.expires_at:
            from django.conf import settings
            hours = getattr(settings, 'CONVERTED_FILE_EXPIRY_HOURS', 24)
            self.expires_at = timezone.now() + timedelta(hours=hours)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if file has expired."""
        return timezone.now() > self.expires_at
    
    def record_download(self):
        """Record a download event."""
        self.download_count += 1
        self.last_downloaded_at = timezone.now()
        self.save(update_fields=['download_count', 'last_downloaded_at'])


class ToolUsageLog(models.Model):
    """
    Logs tool usage for analytics and rate limiting.
    Lightweight model for tracking all operations.
    """
    id = models.BigAutoField(primary_key=True)
    
    tool_name = models.CharField(
        max_length=50,
        db_index=True,
        help_text='Name of the tool used (e.g., audio_convert, video_trim)'
    )
    
    client_ip = models.GenericIPAddressField(db_index=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    
    used_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    success = models.BooleanField(default=True)
    
    # Optional: link to conversion job
    conversion_job = models.ForeignKey(
        ConversionJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_logs'
    )
    
    # Performance tracking
    processing_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Processing time in milliseconds'
    )
    
    class Meta:
        db_table = 'tool_usage_logs'
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['tool_name', 'used_at']),
            models.Index(fields=['client_ip', 'used_at']),
            models.Index(fields=['success', 'used_at']),
        ]
        verbose_name = 'Tool Usage Log'
        verbose_name_plural = 'Tool Usage Logs'
    
    def __str__(self):
        status = '✓' if self.success else '✗'
        return f'{status} {self.tool_name} @ {self.used_at}'
