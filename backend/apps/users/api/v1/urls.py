"""
URL маршруты для API пользователей и аутентификации (v1).
"""

from django.urls import path

from apps.users.api.v1 import views


app_name = 'users_api_v1'

urlpatterns = [
    path('ping/', views.ping, name='ping'),
]