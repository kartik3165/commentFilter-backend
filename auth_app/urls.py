from django.urls import path
from .views import SendOTPView, VerifyOTPView, LogoutView, CookieTokenRefreshView, ProfileInfoView, CurrentUserView, start_trial_view

urlpatterns = [
    path('send-otp/', SendOTPView.as_view()),
    path('verify-otp/', VerifyOTPView.as_view()),
    path('refresh/', CookieTokenRefreshView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('profile-info/', ProfileInfoView.as_view()),
    path('user/', CurrentUserView.as_view()),
    path('start-trial/', start_trial_view, name='start_trail')
]
