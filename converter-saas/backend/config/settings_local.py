"""
Local settings override for development.
Uses SQLite instead of PostgreSQL for quick local testing.
"""

from .settings import *

# Use SQLite for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Debug mode on
DEBUG = True
ALLOWED_HOSTS = ['*']
