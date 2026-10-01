#!/usr/bin/env sh
set -eu

python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-60}"
python manage.py migrate --noinput
if [ -n "${BOOTSTRAP_ADMIN_USERNAME:-}${BOOTSTRAP_ADMIN_EMAIL:-}${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    python manage.py bootstrap_admin
fi
python manage.py collectstatic --noinput
exec gunicorn auralith_erp.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-3}" --access-logfile - --error-logfile -
