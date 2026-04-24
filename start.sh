#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting deployment script..."

# Run database migrations
# We run this in start.sh because it needs to happen right before the app goes live
echo "Running migrations..."
python manage.py migrate --noinput

# Start the Django Q Cluster in the background
echo "Starting Django Q Cluster..."
python manage.py qcluster &

# Start the Gunicorn web server
echo "Starting Gunicorn server..."
# Using exec to replace the shell process with gunicorn
exec gunicorn leadsAutomation.wsgi --log-file -
