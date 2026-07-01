"""
URL маршруты API пользователей (v1): профиль и связанные операции.

Отделены от urls_auth.py, где живут SMS-логин и refresh-токен —
это разные фичи, держим их в разных модулях по правилу
"organize by feature" (см. docs/guidelines/common/clean_code.md).
"""

from django.urls import URLPattern, URLResolver, path

from apps.users.api.v1 import views

app_name = "users_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("me/", views.UserMeView.as_view(), name="user-me"),
]
