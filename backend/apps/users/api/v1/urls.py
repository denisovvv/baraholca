"""
URL маршруты для API пользователей и аутентификации (v1).
"""

from django.urls import path

from apps.users.api.v1 import views

from rest_framework_simplejwt.views import TokenRefreshView


app_name = 'users_api_v1'

urlpatterns = [
    path('sms/request/', views.SmsRequestView.as_view(), name='sms-request'),
    path('sms/verify/', views.SmsVerifyView.as_view(), name='sms-verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]