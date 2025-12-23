#!/bin/bash

# Converter SaaS Production Deployment Script
# This script is idempotent and can be run multiple times.

set -e

PROJECT_ROOT="/var/www/converter-saas"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$PROJECT_ROOT/venv"

echo "🚀 Starting Deployment..."

# 1. Update system and install dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv nginx postgresql postgresql-contrib ffmpeg libmagic1 certbot python3-certbot-nginx redis-server

# 2. Setup Project Directory (if not exists)
sudo mkdir -p $PROJECT_ROOT
sudo chown -R $USER:$USER $PROJECT_ROOT

# 3. Setup Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate

# 4. Install Requirements
pip install --upgrade pip
pip install -r $BACKEND_DIR/requirements.txt
pip install gunicorn

# 5. Database Migrations
cd $BACKEND_DIR
python manage.py migrate --noinput

# 6. Collect Static Files
python manage.py collectstatic --noinput

# 7. Setup Gunicorn Systemd Service
sudo cp $BACKEND_DIR/deploy/gunicorn.service /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl restart gunicorn

# 8. Setup Nginx Configuration
sudo cp $BACKEND_DIR/deploy/nginx.conf /etc/nginx/sites-available/converter-saas
sudo ln -sf /etc/nginx/sites-available/converter-saas /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

echo "✅ Deployment Complete!"
echo "Next Step: Configure your .env file in $BACKEND_DIR and run Certbot for HTTPS."
