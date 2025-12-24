#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🚀 Starting Production Entrypoint..."

# Apply database migrations
echo "📦 Applying database migrations..."
python manage.py migrate --noinput

# Collect static files (already done in Dockerfile, but safe to repeat if needed)
# echo "🎨 Collecting static files..."
# python manage.py collectstatic --noinput

echo "✅ Migrations complete. Starting server..."

# Start Gunicorn
exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application
