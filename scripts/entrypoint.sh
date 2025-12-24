#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🚀 Starting Converter SaaS..."

# Run migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput || true

# Start Gunicorn with config file
echo "🌐 Starting Gunicorn server with optimized configuration..."
exec gunicorn config.wsgi:application --config gunicorn.conf.py
