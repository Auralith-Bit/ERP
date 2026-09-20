FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --no-input || true

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn auralith_erp.wsgi:application --bind 0.0.0.0:8000"]
