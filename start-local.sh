#!/usr/bin/env sh
set -eu

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

python manage.py migrate
python manage.py collectstatic --no-input
python manage.py runserver 0.0.0.0:8000
