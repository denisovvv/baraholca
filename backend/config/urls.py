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
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/auth/", include("apps.users.api.v1.urls_auth")),
    path("api/v1/users/", include("apps.users.api.v1.urls_user")),
    path("api/v1/catalog/", include("apps.catalog.api.v1.urls")),
    path("api/v1/favorites/", include("apps.cart.api.v1.urls_favorite")),
    path("api/v1/cart/", include("apps.cart.api.v1.urls_cart")),
    path("api/v1/orders/", include("apps.orders.api.v1.urls")),
    path("api/v1/reviews/", include("apps.reviews.api.v1.urls")),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Media files (uploaded photos) in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
