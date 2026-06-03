from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('erp_app.urls')),
]

# Serve media files in all environments (Render uses ephemeral storage,
# but this keeps uploads working until you add cloud storage like S3)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Static files are handled by WhiteNoise in production, only need this locally
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
