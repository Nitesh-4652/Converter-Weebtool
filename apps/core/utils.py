"""
Core Utilities for File Converter SaaS.
FFmpeg wrapper, file handling, and helper functions.
"""

import os
import subprocess
import uuid
import json
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone


# ============================================
# FILE UTILITIES
# ============================================

def get_file_extension(filename: str) -> str:
    """Extract file extension (lowercase, without dot)."""
    if '.' in filename:
        return filename.rsplit('.', 1)[-1].lower()
    return ''


def get_mime_type(file_path: str) -> str:
    """Get MIME type of a file."""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'


def generate_output_filename(original_name: str, output_format: str) -> str:
    """Generate output filename with new extension."""
    base_name = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
    unique_id = uuid.uuid4().hex[:8]
    return f'{base_name}_{unique_id}.{output_format}'


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def ensure_directory(path: str) -> None:
    """Ensure directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage and display.
    Removes unsafe characters but preserves readability.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename safe for filesystems
    """
    import re
    
    # Remove or replace unsafe characters
    # Keep alphanumeric, spaces, hyphens, underscores, dots
    sanitized = re.sub(r'[^\w\s\-\.]', '_', filename)
    
    # Remove multiple consecutive underscores/spaces
    sanitized = re.sub(r'_{2,}', '_', sanitized)
    sanitized = re.sub(r'\s{2,}', ' ', sanitized)
    
    # Trim and limit length
    sanitized = sanitized.strip(' _.')[:255]
    
    return sanitized or 'file'


def generate_clean_output_filename(original_name: str, output_format: str) -> str:
    """
    Generate clean output filename for user download.
    No hashes, just original name + new extension.
    
    Args:
        original_name: Original filename from user upload
        output_format: Target format extension
    
    Returns:
        Clean filename like "song.mp3" instead of "abc123_def456_song.mp3"
    """
    # Extract base name (remove extension)
    base_name = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
    
    # Sanitize for safety
    clean_base = sanitize_filename(base_name)
    
    # Return clean name with new extension
    return f'{clean_base}.{output_format.lower()}'


def get_client_ip(request) -> str:
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def get_user_agent(request) -> str:
    """Extract user agent from request."""
    return request.META.get('HTTP_USER_AGENT', '')[:500]


# ============================================
# FFMPEG UTILITIES
# ============================================

class FFmpegError(Exception):
    """Custom exception for FFmpeg errors."""
    pass


def get_ffmpeg_path() -> str:
    """Get FFmpeg executable path."""
    return getattr(settings, 'FFMPEG_PATH', 'ffmpeg')


def get_ffprobe_path() -> str:
    """Get FFprobe executable path."""
    return getattr(settings, 'FFPROBE_PATH', 'ffprobe')


def get_media_info(file_path: str) -> Dict[str, Any]:
    """
    Get media file information using ffprobe.
    Returns duration, format, streams info.
    """
    ffprobe = get_ffprobe_path()
    
    cmd = [
        ffprobe,
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        file_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise FFmpegError(f'FFprobe error: {result.stderr}')
        
        return json.loads(result.stdout)
    
    except subprocess.TimeoutExpired:
        raise FFmpegError('FFprobe timeout')
    except json.JSONDecodeError:
        raise FFmpegError('Invalid FFprobe output')
    except FileNotFoundError:
        raise FFmpegError('FFprobe not found. Please install FFmpeg.')


def get_duration(file_path: str) -> Optional[float]:
    """Get media duration in seconds."""
    try:
        info = get_media_info(file_path)
        duration = info.get('format', {}).get('duration')
        if duration:
            return float(duration)
    except (FFmpegError, ValueError, KeyError):
        pass
    return None


def run_ffmpeg(
    input_path: str,
    output_path: str,
    options: List[str] = None,
    timeout: int = 300
) -> bool:
    """
    Run FFmpeg command with given options.
    
    Args:
        input_path: Input file path
        output_path: Output file path
        options: Additional FFmpeg options
        timeout: Command timeout in seconds
    
    Returns:
        True if successful, raises FFmpegError otherwise
    """
    ffmpeg = get_ffmpeg_path()
    
    # PERFORMANCE: Use all CPU cores for faster encoding
    cmd = [ffmpeg, '-y', '-threads', '0', '-i', input_path]
    
    if options:
        cmd.extend(options)
    
    cmd.append(output_path)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            error_msg = result.stderr[-500:] if result.stderr else 'Unknown error'
            raise FFmpegError(f'FFmpeg conversion failed: {error_msg}')
        
        return True
    
    except subprocess.TimeoutExpired:
        raise FFmpegError(f'FFmpeg timeout after {timeout} seconds')
    except FileNotFoundError:
        raise FFmpegError('FFmpeg not found. Please install FFmpeg.')


# ============================================
# AUDIO CONVERSION UTILITIES
# ============================================

# Codec-specific configuration with bitrate limits
# OPUS: max ~256kbps for reliable encoding (512kbps theoretical max for stereo)
# AAC: max ~320kbps
# MP3: max 320kbps
# Vorbis: max ~500kbps but ~256kbps is practical
AUDIO_CODEC_MAP = {
    'mp3': {
        'codec': 'libmp3lame',
        'options': ['-q:a', '2'],
        'max_bitrate': 320,  # kbps
        'default_bitrate': 192
    },
    'wav': {
        'codec': 'pcm_s16le',
        'options': [],
        'max_bitrate': None,  # Lossless, no bitrate
        'default_bitrate': None
    },
    'aac': {
        'codec': 'aac',
        'options': [],
        'max_bitrate': 320,
        'default_bitrate': 192
    },
    'm4a': {
        'codec': 'aac',
        'options': [],
        'max_bitrate': 320,
        'default_bitrate': 192
    },
    'flac': {
        'codec': 'flac',
        # PERFORMANCE: compression_level 5 is faster than default 8, minimal size difference
        'options': ['-compression_level', '5'],
        'max_bitrate': None,  # Lossless
        'default_bitrate': None
    },
    'ogg': {
        'codec': 'libvorbis',
        'options': ['-q:a', '6'],
        'max_bitrate': 256,
        'default_bitrate': 192
    },
    'opus': {
        'codec': 'libopus',
        # PERFORMANCE: compression_level 5 is faster than 10, good quality balance
        'options': ['-vbr', 'on', '-compression_level', '5'],
        'max_bitrate': 256,  # Safe max for OPUS (actual limit is ~512 for stereo)
        'default_bitrate': 128,
        'recommended_max': 256  # For best quality equivalent to MP3 320
    },
    'aiff': {
        'codec': 'pcm_s16be',
        'options': [],
        'max_bitrate': None,
        'default_bitrate': None
    },
    'wma': {
        'codec': 'wmav2',
        'options': [],
        'max_bitrate': 320,
        'default_bitrate': 192
    },
    'amr': {
        'codec': 'libopencore_amrnb',
        'options': ['-ar', '8000', '-ac', '1'],
        'max_bitrate': 12,  # AMR-NB max
        'default_bitrate': 12
    },
    'ac3': {
        'codec': 'ac3',
        'options': [],
        'max_bitrate': 640,
        'default_bitrate': 384
    },
    'ape': {
        'codec': 'ape',
        'options': [],
        'max_bitrate': None,
        'default_bitrate': None
    },
    'caf': {
        'codec': 'pcm_s16le',
        'options': [],
        'max_bitrate': None,
        'default_bitrate': None
    },
}


def validate_audio_bitrate(output_format: str, requested_bitrate: str) -> tuple[str, str]:
    """
    Validate and adjust bitrate for codec limitations.
    
    Args:
        output_format: Target audio format
        requested_bitrate: Requested bitrate (e.g., '320k', '192k')
    
    Returns:
        Tuple of (validated_bitrate, warning_message or None)
    """
    format_config = AUDIO_CODEC_MAP.get(output_format.lower(), {})
    max_bitrate = format_config.get('max_bitrate')
    default_bitrate = format_config.get('default_bitrate')
    
    # If no bitrate limit (lossless formats), return as-is
    if max_bitrate is None:
        return requested_bitrate, None
    
    # Parse requested bitrate
    try:
        # Handle formats like '320k', '192k', '128'
        bitrate_str = requested_bitrate.lower().replace('k', '').replace('kbps', '')
        bitrate_value = int(bitrate_str)
    except (ValueError, AttributeError):
        # Invalid format, use default
        return f'{default_bitrate}k', f'Invalid bitrate format, using {default_bitrate}kbps'
    
    # Check if exceeds max
    if bitrate_value > max_bitrate:
        warning = (
            f'{output_format.upper()} does not support {bitrate_value}kbps. '
            f'Maximum supported is {max_bitrate}kbps. Using {max_bitrate}kbps instead.'
        )
        return f'{max_bitrate}k', warning
    
    return requested_bitrate, None


def get_opus_quality_note() -> str:
    """
    Returns explanation about OPUS quality.
    OPUS at 128-256kbps is perceptually equivalent to MP3 320kbps.
    """
    return (
        "Note: OPUS is a highly efficient codec. "
        "OPUS at 128kbps ≈ MP3 256kbps quality. "
        "OPUS at 256kbps ≈ MP3 320kbps or better quality. "
        "320kbps is not needed for OPUS - 256kbps is the recommended maximum."
    )


def convert_audio(
    input_path: str,
    output_path: str,
    output_format: str,
    options: Dict[str, Any] = None
) -> str:
    """
    Convert audio file to specified format with codec-aware bitrate handling.
    
    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        output_format: Target audio format
        options: Additional options (bitrate, sample_rate, etc.)
    
    Returns:
        Output file path
    
    Raises:
        FFmpegError: If conversion fails
    """
    options = options or {}
    
    # Get codec and default options for format
    format_config = AUDIO_CODEC_MAP.get(output_format.lower(), {})
    codec = format_config.get('codec', 'copy')
    ffmpeg_options = format_config.get('options', []).copy()
    default_bitrate = format_config.get('default_bitrate')
    
    # PERFORMANCE: Skip video stream entirely (faster processing)
    ffmpeg_options.extend(['-vn'])
    
    # Add codec
    if codec != 'copy':
        ffmpeg_options.extend(['-acodec', codec])
    
    # Handle bitrate with validation
    if 'bitrate' in options and options['bitrate']:
        validated_bitrate, warning = validate_audio_bitrate(
            output_format, 
            options['bitrate']
        )
        if validated_bitrate:
            ffmpeg_options.extend(['-b:a', validated_bitrate])
        # Warning is logged but conversion proceeds with safe value
        if warning:
            import logging
            logging.warning(f'Audio conversion: {warning}')
    elif default_bitrate:
        # Use default bitrate for lossy formats
        ffmpeg_options.extend(['-b:a', f'{default_bitrate}k'])
    
    # Add sample rate if specified
    if 'sample_rate' in options:
        ffmpeg_options.extend(['-ar', str(options['sample_rate'])])
    
    # Add channels if specified
    if 'channels' in options:
        ffmpeg_options.extend(['-ac', str(options['channels'])])
    
    # Run FFmpeg
    run_ffmpeg(input_path, output_path, ffmpeg_options)
    
    return output_path


def trim_audio(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    copy_mode: bool = True
) -> str:
    """
    Trim audio file between start and end time.
    
    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        start_time: Start time in seconds
        end_time: End time in seconds
        copy_mode: If True, use stream copy (faster, no re-encoding)
    
    Returns:
        Output file path
    """
    duration = end_time - start_time
    
    ffmpeg_options = [
        '-ss', str(start_time),
        '-t', str(duration)
    ]
    
    if copy_mode:
        ffmpeg_options.extend(['-c', 'copy'])
    
    run_ffmpeg(input_path, output_path, ffmpeg_options)
    
    return output_path


def extract_audio_from_video(
    input_path: str,
    output_path: str,
    output_format: str,
    options: Dict[str, Any] = None
) -> str:
    """
    Extract audio track from video file.
    
    Args:
        input_path: Path to input video file
        output_path: Path for output audio file
        output_format: Target audio format
        options: Additional options
    
    Returns:
        Output file path
    """
    options = options or {}
    
    # Get codec for format
    format_config = AUDIO_CODEC_MAP.get(output_format.lower(), {})
    codec = format_config.get('codec', 'copy')
    ffmpeg_options = format_config.get('options', []).copy()
    
    # No video
    ffmpeg_options.extend(['-vn'])
    
    # Add audio codec
    if codec != 'copy':
        ffmpeg_options.extend(['-acodec', codec])
    
    run_ffmpeg(input_path, output_path, ffmpeg_options)
    
    return output_path


# ============================================
# VIDEO CONVERSION UTILITIES
# ============================================

# Format-specific configuration with codec requirements and limitations
# 3GP is a legacy mobile format with strict requirements:
#   - Video: mpeg4 (MPEG-4 Part 2) or h264 for newer devices
#   - Audio: aac (libfdk_aac/aac) is most compatible
#   - Max resolution: 352x288 (CIF) for classic, 640x480 for modern
#   - Frame rate: typically 15-25 fps
VIDEO_CODEC_MAP = {
    'mp4': {
        'vcodec': 'libx264',
        'acodec': 'aac',
        # PERFORMANCE: 'veryfast' preset is 3-4x faster than 'medium' with ~10% larger file
        'options': ['-preset', 'veryfast', '-crf', '23', '-movflags', '+faststart'],
        'max_resolution': None,
        'legacy': False
    },
    'mkv': {
        'vcodec': 'libx264',
        'acodec': 'aac',
        # PERFORMANCE: 'veryfast' preset for speed
        'options': ['-preset', 'veryfast', '-crf', '23'],
        'max_resolution': None,
        'legacy': False
    },
    'avi': {
        'vcodec': 'libxvid',
        'acodec': 'mp3',
        'options': ['-q:v', '4'],
        'max_resolution': None,
        'legacy': False
    },
    'mov': {
        'vcodec': 'libx264',
        'acodec': 'aac',
        # PERFORMANCE: 'veryfast' preset + faststart for web
        'options': ['-preset', 'veryfast', '-movflags', '+faststart'],
        'max_resolution': None,
        'legacy': False
    },
    'webm': {
        'vcodec': 'libvpx-vp9',
        'acodec': 'libopus',
        # PERFORMANCE: deadline=good is faster than default, -cpu-used 4 for speed
        'options': ['-crf', '30', '-b:v', '0', '-deadline', 'good', '-cpu-used', '4'],
        'max_resolution': None,
        'legacy': False
    },
    'flv': {
        'vcodec': 'flv1',
        'acodec': 'mp3',
        'options': [],
        'max_resolution': None,
        'legacy': False
    },
    'wmv': {
        'vcodec': 'wmv2',
        'acodec': 'wmav2',
        'options': [],
        'max_resolution': None,
        'legacy': False
    },
    '3gp': {
        'vcodec': 'mpeg4',  # MPEG-4 Part 2 - most compatible for 3GP
        'acodec': 'aac',
        'options': [
            '-b:v', '384k',      # Safe video bitrate
            '-b:a', '64k',       # Low audio bitrate for mobile
            '-ar', '22050',      # Audio sample rate (22.05 kHz)
            '-ac', '1',          # Mono audio for compatibility
            '-r', '15',          # 15 fps for smooth playback on old devices
        ],
        'max_resolution': '320x240',  # QVGA - maximum safe resolution
        'legacy': True,
        'force_resolution': True  # Always apply resolution limit
    },
    'mpg': {
        'vcodec': 'mpeg2video',
        'acodec': 'mp2',
        'options': [],
        'max_resolution': None,
        'legacy': False
    },
    'mpeg': {
        'vcodec': 'mpeg2video',
        'acodec': 'mp2',
        'options': [],
        'max_resolution': None,
        'legacy': False
    },
    'ts': {
        'vcodec': 'mpeg2video',
        'acodec': 'mp2',
        'options': [],
        'max_resolution': None,
        'legacy': False
    },
    'm4v': {
        'vcodec': 'libx264',
        'acodec': 'aac',
        # PERFORMANCE: 'veryfast' preset + faststart
        'options': ['-preset', 'veryfast', '-movflags', '+faststart'],
        'max_resolution': None,
        'legacy': False
    },
    'ogv': {
        'vcodec': 'libtheora',
        'acodec': 'libvorbis',
        'options': ['-q:v', '6'],
        'max_resolution': None,
        'legacy': False
    },
}


def get_3gp_format_info() -> str:
    """
    Returns information about 3GP format limitations.
    Useful for user-facing error messages.
    """
    return (
        "3GP is a legacy mobile format with strict limitations:\n"
        "• Maximum resolution: 320x240 (QVGA)\n"
        "• Video codec: MPEG-4 Part 2\n"
        "• Audio: Mono AAC at 64kbps\n"
        "• Frame rate: 15 fps\n"
        "• Best for: Old mobile phones, small file sizes\n"
        "Note: Quality will be significantly reduced compared to modern formats."
    )


def validate_video_format_options(output_format: str, options: Dict[str, Any]) -> tuple:
    """
    Validate and adjust options based on format-specific limitations.
    
    Args:
        output_format: Target video format
        options: User-provided options
    
    Returns:
        Tuple of (adjusted_options, warning_message or None)
    """
    format_config = VIDEO_CODEC_MAP.get(output_format.lower(), {})
    warning = None
    adjusted_options = options.copy() if options else {}
    
    # Check if format has resolution limits
    max_res = format_config.get('max_resolution')
    force_res = format_config.get('force_resolution', False)
    
    if max_res and force_res:
        # For legacy formats like 3GP, always enforce resolution
        if 'resolution' in adjusted_options:
            # User specified resolution - check if it exceeds limit
            user_res = adjusted_options['resolution']
            max_width, max_height = map(int, max_res.split('x'))
            try:
                user_width, user_height = map(int, user_res.split('x'))
                if user_width > max_width or user_height > max_height:
                    adjusted_options['resolution'] = max_res
                    warning = f'{output_format.upper()} format limits resolution to {max_res}. Using maximum supported resolution.'
            except ValueError:
                adjusted_options['resolution'] = max_res
        else:
            # No resolution specified - apply format limit
            adjusted_options['resolution'] = max_res
    
    # For legacy formats, ignore user bitrate settings
    if format_config.get('legacy', False):
        if 'video_bitrate' in adjusted_options:
            del adjusted_options['video_bitrate']
        if 'audio_bitrate' in adjusted_options:
            del adjusted_options['audio_bitrate']
        if warning:
            warning += ' Bitrate settings are ignored for legacy formats.'
        else:
            warning = f'{output_format.upper()} is a legacy format. Using optimized settings for compatibility.'
    
    return adjusted_options, warning


def convert_video(
    input_path: str,
    output_path: str,
    output_format: str,
    options: Dict[str, Any] = None
) -> str:
    """
    Convert video file to specified format with format-aware handling.
    
    Args:
        input_path: Path to input video file
        output_path: Path for output file
        output_format: Target video format
        options: Additional options (resolution, bitrate, etc.)
    
    Returns:
        Output file path
    
    Raises:
        FFmpegError: If conversion fails
    """
    options = options or {}
    output_format_lower = output_format.lower()
    
    # Validate and adjust options for format-specific limitations
    adjusted_options, warning = validate_video_format_options(output_format_lower, options)
    
    if warning:
        import logging
        logging.info(f'Video conversion: {warning}')
    
    # Get codecs for format
    format_config = VIDEO_CODEC_MAP.get(output_format_lower, {})
    vcodec = format_config.get('vcodec', 'copy')
    acodec = format_config.get('acodec', 'copy')
    ffmpeg_options = format_config.get('options', []).copy()
    
    # Add video codec
    ffmpeg_options.extend(['-vcodec', vcodec])
    
    # Add audio codec
    ffmpeg_options.extend(['-acodec', acodec])
    
    # Add resolution - use adjusted options which may have format-specific limits
    if 'resolution' in adjusted_options and adjusted_options['resolution']:
        # Check if resolution is already in ffmpeg_options (from format config)
        has_resolution = any(opt == '-s' for opt in ffmpeg_options)
        if not has_resolution:
            ffmpeg_options.extend(['-s', adjusted_options['resolution']])
    
    # Add video bitrate if specified (and not a legacy format)
    if 'video_bitrate' in adjusted_options and adjusted_options['video_bitrate']:
        ffmpeg_options.extend(['-b:v', adjusted_options['video_bitrate']])
    
    # Add audio bitrate if specified (and not a legacy format)
    if 'audio_bitrate' in adjusted_options and adjusted_options['audio_bitrate']:
        ffmpeg_options.extend(['-b:a', adjusted_options['audio_bitrate']])
    
    # For strict formats, add pixel format for compatibility
    if output_format_lower in ['3gp', 'flv', 'wmv']:
        ffmpeg_options.extend(['-pix_fmt', 'yuv420p'])
    
    run_ffmpeg(input_path, output_path, ffmpeg_options)
    
    return output_path


def trim_video(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    copy_mode: bool = True
) -> str:
    """
    Trim video file between start and end time.
    
    Args:
        input_path: Path to input video file
        output_path: Path for output file
        start_time: Start time in seconds
        end_time: End time in seconds
        copy_mode: If True, use stream copy (faster, no re-encoding)
    
    Returns:
        Output file path
    """
    duration = end_time - start_time
    
    ffmpeg_options = [
        '-ss', str(start_time),
        '-t', str(duration)
    ]
    
    if copy_mode:
        ffmpeg_options.extend(['-c', 'copy'])
    
    run_ffmpeg(input_path, output_path, ffmpeg_options)
    
    return output_path


# ============================================
# RATE LIMITING UTILITIES
# ============================================

def check_rate_limit(client_ip: str, tool_name: str = None) -> Tuple[bool, int]:
    """
    Check if client has exceeded rate limit.
    
    Args:
        client_ip: Client IP address
        tool_name: Optional tool name to check specific limit
    
    Returns:
        Tuple of (is_allowed, remaining_requests)
    """
    from .models import ToolUsageLog
    from datetime import timedelta
    
    limit = getattr(settings, 'RATE_LIMIT_REQUESTS_PER_HOUR', 100)
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    # Count requests in last hour
    query = ToolUsageLog.objects.filter(
        client_ip=client_ip,
        used_at__gte=one_hour_ago
    )
    
    if tool_name:
        query = query.filter(tool_name=tool_name)
    
    count = query.count()
    remaining = max(0, limit - count)
    is_allowed = count < limit
    
    return is_allowed, remaining


def log_tool_usage(
    tool_name: str,
    client_ip: str,
    success: bool = True,
    conversion_job=None,
    processing_time_ms: int = None,
    user_agent: str = ''
) -> None:
    """
    Log tool usage for analytics.
    
    Args:
        tool_name: Name of the tool
        client_ip: Client IP address
        success: Whether operation was successful
        conversion_job: Optional related ConversionJob
        processing_time_ms: Processing time in milliseconds
        user_agent: User agent string
    """
    from .models import ToolUsageLog
    
    ToolUsageLog.objects.create(
        tool_name=tool_name,
        client_ip=client_ip,
        success=success,
        conversion_job=conversion_job,
        processing_time_ms=processing_time_ms,
        user_agent=user_agent
    )
