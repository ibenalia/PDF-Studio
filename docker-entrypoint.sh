#!/bin/bash
set -e

# Create data directories if they don't exist and ensure proper permissions
mkdir -p /app/data/uploads /app/data/temp /app/data/processed
chown -R pdfeditor:pdfeditor /app/data

# First arg is `-f` or `--some-option`
if [ "${1#-}" != "$1" ]; then
    set -- gunicorn --bind 0.0.0.0:5000 --workers 3 run:app "$@"
fi

# If the command starts with an option, prepend gunicorn
if [ "$1" = 'gunicorn' ] || [ "$1" = 'flask' ]; then
    # Use gosu to drop to a non-root user
    exec gosu pdfeditor "$@"
else
    # Otherwise, run the command as is
    exec "$@"
fi 