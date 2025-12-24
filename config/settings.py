"""
Django settings for converter-saas project.
Production-ready configuration for file converter SaaS.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-change-this-in-production-use-env-variable'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') + ['.ngrok.io', '.ngrok-free.app', '.ngrok-free.dev', '.railway.app', '.up.railway.app']


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'apps.core',
    'apps.audio',
    'apps.video',
    'apps.image',
    'apps.pdf',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database Configuration - Unified SQLite/Postgres support
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (uploads and outputs)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Upload/Output directories
UPLOAD_DIR = MEDIA_ROOT / 'uploads'
OUTPUT_DIR = MEDIA_ROOT / 'outputs'

# Create directories if they don't exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}


# CORS Configuration
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',')

CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only in development

# Expose headers for download functionality
CORS_EXPOSE_HEADERS = [
    'Content-Disposition',
    'Content-Type',
    'Content-Length',
]

# CSRF Configuration for Ngrok and Railway
CSRF_TRUSTED_ORIGINS = ['https://*.ngrok.io', 'https://*.ngrok-free.app', 'https://*.ngrok-free.dev', 'https://*.railway.app', 'https://*.up.railway.app']


# File Upload Configuration
# Increased to 500MB to support large video files
FILE_UPLOAD_MAX_MEMORY_SIZE = 500 * 1024 * 1024  # 500MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 500 * 1024 * 1024  # 500MB
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB max file size


# Supported Formats Configuration
SUPPORTED_AUDIO_FORMATS = [
    'mp3', 'wav', 'aac', 'm4a', 'flac', 'ogg', 'opus',
    'aiff', 'alac', 'wma', 'amr', 'ac3', 'pcm', 'ape', 'caf'
]

SUPPORTED_VIDEO_FORMATS = [
    'mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'wmv',
    '3gp', 'mpg', 'mpeg', 'ts', 'm4v', 'ogv',
    'f4v', 'vob', 'rm', 'rmvb'
]

SUPPORTED_IMAGE_FORMATS = [
    'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg', 'bmp', 'tiff', 'tif',
    'ico', 'heic', 'heif', 'raw', 'psd', 'ai', 'eps', 'avif',
    'ppm', 'pgm'
]

SUPPORTED_DOCUMENT_FORMATS = [
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'html', 'md', 'csv', 'pdf'
]


# FFmpeg Configuration
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', 'ffmpeg')
FFPROBE_PATH = os.environ.get('FFPROBE_PATH', 'ffprobe')


# File Expiry Settings (in hours) - Backup cleanup for missed downloads
CONVERTED_FILE_EXPIRY_HOURS = 1


# Rate Limiting (requests per hour per IP)
RATE_LIMIT_REQUESTS_PER_HOUR = 100


# ============================================
# CELERY CONFIGURATION
# ============================================

# Feature flag for async conversion (Switch to True for background processing)
USE_ASYNC_CONVERSION = os.environ.get('USE_ASYNC_CONVERSION', 'False').lower() == 'true'

# Redis connection details
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Task configuration
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 3300  # 55 min soft limit

# Reliability
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True

# Celery Beat Schedule - Periodic Tasks
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-files': {
        'task': 'apps.core.tasks.cleanup_expired_files',
        'schedule': 30 * 60,  # Every 30 minutes
    },
}

# ============================================
# LOGGING CONFIGURATION
# ============================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose' if not DEBUG else 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': True,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': True,
        },
    },
}

# Health Check Settings
HEALTH_CHECK_SENSITIVE_INFO = os.environ.get('HEALTH_CHECK_SENSITIVE_INFO', 'False').lower() == 'true'

