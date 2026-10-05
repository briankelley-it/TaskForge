#!/bin/sh
# Development start-up for the "web" container.
set -e

# Build the CSS once, then keep rebuilding it in the background when templates change.
# --poll is needed because file-change events don't cross a Windows/macOS bind mount.
tailwindcss -i assets/tailwind.css -o static/css/app.css
tailwindcss -i assets/tailwind.css -o static/css/app.css --watch=always --poll=1000 &

python manage.py migrate --noinput
# First start only: create the demo workspace so there's something to look at.
python manage.py seed_demo --if-missing
exec python manage.py runserver 0.0.0.0:8000
