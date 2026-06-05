"""
Корневой маршрутизатор проекта Baraxolka.

Все API-маршруты подключаются под префиксом /api/v1/
Версионирование позволяет вводить /api/v2/ для ломающих изменений
без поломки старых клиентов.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/auth/', include('apps.users.api.v1.urls')),
    path('api/v1/catalog/', include('apps.catalog.api.v1.urls')),
]

# Media files (uploaded photos) in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)