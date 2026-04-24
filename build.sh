#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting Build script..."

# Install dependencies
echo "Installing requirements..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput