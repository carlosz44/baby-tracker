#!/bin/bash
set -e

# Start Tailwind CSS watcher in the background
tailwindcss -i static/css/input.css -o static/css/output.css --watch &

# Run Django development server
python manage.py runserver 0.0.0.0:8000
