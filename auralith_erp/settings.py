from pathlib import Path
import os
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def get_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


# ---------------------------------------------------------------------------
# Core security — all pulled from environment variables
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-development-only')

DEBUG = get_bool(os.environ.get('DEBUG'), False)
if not DEBUG and SECRET_KEY == 'django-insecure-local-development-only':
    raise RuntimeError('Set SECRET_KEY to a strong, private value in production.')

allowed_hosts = os.environ.get(
    'ALLOWED_HOSTS',
    'erp.auralithbit.com.np,erp-1-u9vu.onrender.com,erp-akwh.onrender.com,localhost,127.0.0.1'
)
ALLOWED_HOSTS = []
CSRF_TRUSTED_ORIGINS = []
for configured_host in allowed_hosts.split(','):
    configured_host = configured_host.strip()
    if not configured_host:
        continue
    parsed_host = urlsplit(configured_host if '://' in configured_host else f'//{configured_host}')
    if parsed_host.hostname:
        ALLOWED_HOSTS.append(parsed_host.hostname)
        if parsed_host.scheme in {'http', 'https'}:
            CSRF_TRUSTED_ORIGINS.append(f'{parsed_host.scheme}://{parsed_host.netloc}')
        elif parsed_host.hostname in {'localhost', '127.0.0.1'}:
            CSRF_TRUSTED_ORIGINS.extend([
                f'http://{parsed_host.netloc}', f'https://{parsed_host.netloc}',
            ])
        else:
            CSRF_TRUSTED_ORIGINS.append(f'https://{parsed_host.netloc}')

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['erp.auralithbit.com.np', 'localhost', '127.0.0.1']

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'erp_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # serves static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'auralith_erp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'erp_app.context_processors.sidebar_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'auralith_erp.wsgi.application'

# ---------------------------------------------------------------------------
# Database — PostgreSQL on Render, SQLite for local dev
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=60)
    }
elif DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    raise RuntimeError('Set DATABASE_URL to a persistent shared database for deployment.')

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Email — Gmail SMTP, credentials from environment variables only
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = get_bool(os.environ.get('EMAIL_USE_TLS'), True)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'Auralith ERP <noreply@example.com>',
)
