from django.urls import path
from .views import (
    register, login, logout, verify_otp, google_oauth,
    password_reset, user_profile, CustomTokenRefreshView
)

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('verify-otp/', verify_otp, name='verify_otp'),
    path('google-oauth/', google_oauth, name='google_oauth'),
    path('password-reset/', password_reset, name='password_reset'),
    path('user/', user_profile, name='user_profile'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
]