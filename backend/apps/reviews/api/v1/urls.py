"""
URL-маршруты API отзывов.

GET    /api/v1/reviews/?product={id} — список отзывов товара
POST   /api/v1/reviews/              — создать отзыв
PATCH  /api/v1/reviews/{id}/         — редактировать свой
DELETE /api/v1/reviews/{id}/         — удалить свой
"""

from django.urls import URLPattern, URLResolver, path

from apps.reviews.api.v1 import views

app_name = "reviews_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views.ReviewsView.as_view(), name="reviews"),
    path("<int:pk>/", views.ReviewDetailView.as_view(), name="detail"),
]
