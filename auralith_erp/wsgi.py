"""
WSGI config for auralith_erp project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auralith_erp.settings')

application = get_wsgi_application()
application = WhiteNoise(application, root=settings.STATIC_ROOT)
# Media files are served via S3 (or django serve view locally), no need for WhiteNoise
# application.add_files(settings.MEDIA_ROOT, prefix='media/')
