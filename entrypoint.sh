#!/usr/bin/env sh
set -eu

python manage.py migrate
python manage.py collectstatic --no-input || true
exec gunicorn auralith_erp.wsgi:application --bind 0.0.0.0:8000
