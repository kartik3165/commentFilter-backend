from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.models import SocialAccount
from .models import User, AuthAuditLog, OTPVerification, UserRefreshToken
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    OTPVerificationSerializer, PasswordResetSerializer
)
from .utils import create_audit_log, get_client_ip
import logging
import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings

audit_logger = logging.getLogger('auth_app.audit')

def _store_refresh_token(user, refresh, request):
    device_info = request.META.get("HTTP_USER_AGENT", "Unknown")
    UserRefreshToken.objects.create(user=user, token=str(refresh), device_info=device_info)

def _set_refresh_cookie(response, refresh, request):
    response.set_cookie(
        'refresh_token',
        str(refresh),
        max_age=7*24*60*60,
        httponly=True,
        secure=request.is_secure(),
        samesite='Lax'
    )
    return response




@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def register(request):
    serializer = RegisterSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        user = serializer.save()
        create_audit_log(user, 'signup', get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''), {'email': user.email})
        return Response({'message': 'User registered successfully. Please verify your phone number.', 'user_id': user.id}, status=201)
    return Response(serializer.errors, status=400)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def login(request):
    serializer = LoginSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        user = serializer.validated_data['user']
        if not user.is_phone_verified:
            return Response({'message': 'Please verify your phone number first', 'requires_otp': True, 'user_id': user.id}, status=200)

        user.unlock_account()
        refresh = RefreshToken.for_user(user)
        _store_refresh_token(user, refresh, request)

        response = Response({'access_token': str(refresh.access_token), 'user': UserSerializer(user).data, 'message': 'Login successful'})
        _set_refresh_cookie(response, refresh, request)

        create_audit_log(user, 'login_success', get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))
        return response
    return Response(serializer.errors, status=401)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def verify_otp(request):
    serializer = OTPVerificationSerializer(data=request.data)
    if serializer.is_valid():
        firebase_id_token = serializer.validated_data['firebase_id_token']
        phone_number = serializer.validated_data['phone_number']
        decoded_token = auth.verify_id_token(firebase_id_token)
        firebase_phone = decoded_token.get('phone_number')

        if not firebase_phone or firebase_phone != phone_number:
            return Response({'error': 'Invalid phone number in Firebase token'}, status=400)

        otp_verification = OTPVerification.objects.get(phone_number=phone_number, is_verified=False)
        user = otp_verification.user
        otp_verification.is_verified = True
        otp_verification.verified_at = timezone.now()
        otp_verification.firebase_uid = decoded_token.get('uid')
        otp_verification.save()

        user.is_phone_verified = True
        user.phone_number = phone_number
        user.save()

        refresh = RefreshToken.for_user(user)
        _store_refresh_token(user, refresh, request)

        response = Response({'access_token': str(refresh.access_token), 'user': UserSerializer(user).data, 'message': 'Phone verification successful'})
        _set_refresh_cookie(response, refresh, request)

        create_audit_log(user, 'otp_verified', get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''), {'phone_number': phone_number})
        return response

    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def google_oauth(request):
    email = request.data.get('email')
    name = request.data.get('name', '')
    if not email:
        return Response({'error': 'Email required'}, status=400)

    user, created = User.objects.get_or_create(email=email, defaults={'username': email.split('@')[0]})
    if created:
        user.is_email_verified = True
        user.save()

    if not user.is_phone_verified:
        return Response({'message': 'Please verify your phone number', 'requires_otp': True, 'user_id': user.id}, status=200)

    refresh = RefreshToken.for_user(user)
    _store_refresh_token(user, refresh, request)

    response = Response({'access_token': str(refresh.access_token), 'user': UserSerializer(user).data, 'message': 'Google OAuth login successful'})
    _set_refresh_cookie(response, refresh, request)

    create_audit_log(user, 'login_success', get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''), {'method': 'google_oauth'})
    return response
        

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    refresh_token = request.COOKIES.get('refresh_token')
    if refresh_token:
        UserRefreshToken.objects.filter(token=refresh_token).delete()
    response = Response({'message': 'Logout successful'})
    response.delete_cookie('refresh_token')
    create_audit_log(request.user, 'logout', get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))
    return response

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'error': 'No refresh token provided'}, status=400)
        if not UserRefreshToken.objects.filter(token=refresh_token).exists():
            return Response({'error': 'Invalid or expired refresh token'}, status=401)

        request.data['refresh'] = refresh_token
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200 and 'refresh' in response.data:
            new_refresh = response.data['refresh']
            UserRefreshToken.objects.filter(token=refresh_token).delete()
            _store_refresh_token(request.user, new_refresh, request)
            _set_refresh_cookie(response, new_refresh, request)
            del response.data['refresh']  # hide from JSON

        return response

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def password_reset(request):
    serializer = PasswordResetSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            reset_url = f"{request.scheme}://{request.get_host()}/reset-password/{uid}/{token}/"
            
            send_mail(
                'Password Reset Request',
                f'Click the link to reset your password: {reset_url}',
                'noreply@yourdomain.com',
                [email],
                fail_silently=False,
            )
            
            create_audit_log(
                user=user,
                event='password_reset',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={'email_sent': True}
            )
            
        except User.DoesNotExist:
            pass
        
        return Response({
            'message': 'If the email exists, a password reset link has been sent.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)