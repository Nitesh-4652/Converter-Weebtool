"""
Core Admin Configuration.
"""

from django.contrib import admin
from .models import ConversionJob, UploadedFile, ConvertedFile, ToolUsageLog


@admin.register(ConversionJob)
class ConversionJobAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tool_type', 'operation_type', 'status',
        'input_format', 'output_format', 'created_at'
    ]
    list_filter = ['status', 'tool_type', 'operation_type', 'created_at']
    search_fields = ['id', 'client_ip']
    readonly_fields = ['id', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_name', 'file_type', 'file_size', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['original_name']
    readonly_fields = ['id', 'uploaded_at']


@admin.register(ConvertedFile)
class ConvertedFileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'conversion_job', 'output_format',
        'file_size', 'download_count', 'expires_at'
    ]
    list_filter = ['output_format', 'created_at', 'expires_at']
    readonly_fields = ['id', 'created_at']


@admin.register(ToolUsageLog)
class ToolUsageLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'tool_name', 'client_ip', 'success', 'used_at']
    list_filter = ['tool_name', 'success', 'used_at']
    search_fields = ['client_ip', 'tool_name']
    readonly_fields = ['id', 'used_at']
    date_hierarchy = 'used_at'
