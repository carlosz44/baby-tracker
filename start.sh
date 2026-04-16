#!/bin/bash
set -e

# Build Tailwind CSS once, then start watcher in background
tailwindcss -i static/css/input.css -o static/css/output.css
tailwindcss -i static/css/input.css -o static/css/output.css --watch &

# Run Django development server
python manage.py runserver 0.0.0.0:8000
