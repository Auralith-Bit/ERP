from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('erp_app.urls')),
]

# Serve media files in all environments
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Static files are handled by WhiteNoise in production, only need this locally
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
