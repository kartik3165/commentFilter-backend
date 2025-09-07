import re
import uuid
from datetime import timedelta
from django.forms import ValidationError
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
from django_ratelimit.exceptions import Ratelimited
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.models import SocialAccount
from .models import User, AuthAuditLog, OTPVerification, UserRefreshToken
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    OTPVerificationSerializer, PasswordResetSerializer, SendOTPSerializer
)
from .utils import create_audit_log, get_client_ip
import logging
import firebase_admin
from firebase_admin import auth
from django.core.cache import cache
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework.permissions import AllowAny

audit_logger = logging.getLogger('auth_app.audit')

# Utility functions
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

# Phone number validator
def phone_validator(value):
    """Validate phone number format (E.164)"""
    phone_pattern = r'^\+[1-9]\d{1,14}$'
    if not re.match(phone_pattern, value):
        raise ValidationError(
            'Enter a valid phone number in E.164 format (e.g., +1234567890)'
        )
    return value

# Views
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
@permission_classes([AllowAny])
def google_oauth(request):
    token = request.data.get('id_token')
    if not token:
        return Response({'error': 'id_token required'}, status=400)

    try:
        # Verify Google ID token
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request())

        email = idinfo.get('email')
        name = idinfo.get('name', '')

        if not email:
            # Log failed login attempt
            create_audit_log(
                None,
                'login_failed',
                get_client_ip(request),
                request.META.get('HTTP_USER_AGENT', ''),
                {'reason': 'Google token did not provide email'}
            )
            return Response({'error': 'Email not provided by Google'}, status=400)

        # Check if user exists
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': email.split('@')[0], 'is_email_verified': True}
        )

        if created:
            # ✅ Log signup only
            create_audit_log(
                user,
                'signup',
                get_client_ip(request),
                request.META.get('HTTP_USER_AGENT', ''),
                {'method': 'google_oauth'}
            )

            # Ask for phone verification
            return Response(
                {
                    'message': 'User registered successfully. Please verify your phone number.',
                    'requires_otp': True,
                    'user_id': user.id
                },
                status=201
            )

        # Existing user flow → check phone verification
        if not user.is_phone_verified:
            return Response(
                {
                    'message': 'Please verify your phone number',
                    'requires_otp': True,
                    'user_id': user.id
                },
                status=200
            )

        # Issue tokens for existing user
        refresh = RefreshToken.for_user(user)
        _store_refresh_token(user, refresh, request)

        response = Response({
            'access_token': str(refresh.access_token),
            'user': UserSerializer(user).data,
            'message': 'Google OAuth login successful'
        })
        _set_refresh_cookie(response, refresh, request)

        # ✅ Log login success
        create_audit_log(
            user,
            'login_success',
            get_client_ip(request),
            request.META.get('HTTP_USER_AGENT', ''),
            {'method': 'google_oauth'}
        )

        return response

    except ValueError as e:
        # Covers invalid token
        create_audit_log(
            None,
            'login_failed',
            get_client_ip(request),
            request.META.get('HTTP_USER_AGENT', ''),
            {'reason': str(e)}
        )
        return Response({'error': 'Invalid or expired Google token'}, status=400)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def send_firebase_otp(request):
    """
    Production-ready Firebase OTP sending endpoint with serializer validation
    """
    serializer = SendOTPSerializer(data=request.data, context={"request": request})
    
    if serializer.is_valid():
        try:
            phone_number = serializer.validated_data['phone_number']
            user_id = serializer.validated_data.get('user_id')
            
            # Get user if provided
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'Invalid user ID'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check for recent OTP requests
            recent_otp = OTPVerification.objects.filter(
                phone_number=phone_number,
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).first()
            
            if recent_otp:
                return Response(
                    {'error': 'Please wait before requesting a new OTP'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            
            # Create or get OTP verification record
            otp_verification, created = OTPVerification.objects.get_or_create(
                phone_number=phone_number,
                is_verified=False,
                defaults={
                    'user': user,
                    'created_at': timezone.now()
                }
            )
            
            if not created:
                otp_verification.user = user
                otp_verification.created_at = timezone.now()
                otp_verification.save(update_fields=['user', 'created_at'])
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            cache_key = f"otp_session_{session_id}"
            cache.set(cache_key, {
                'phone_number': phone_number,
                'user_id': user_id if user_id else None,
                'otp_verification_id': otp_verification.id
            }, 300)
            
            # Audit logging
            create_audit_log(
                user=user,
                event='otp_requested',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'phone_number': phone_number,
                    'method': 'firebase',
                    'session_id': session_id
                }
            )
            
            audit_logger.info(f"OTP requested for {phone_number} from IP {get_client_ip(request)}")
            
            return Response({
                'message': 'OTP request initiated successfully',
                'session_id': session_id,
                'expires_in': 300
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            audit_logger.error(f"Error in send_firebase_otp: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def verify_otp(request):
    serializer = OTPVerificationSerializer(data=request.data)
    if serializer.is_valid():
        firebase_id_token = serializer.validated_data['firebase_id_token']
        phone_number = serializer.validated_data['phone_number']
        
        try:
            # Validate phone number format
            phone_validator(phone_number)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            decoded_token = auth.verify_id_token(firebase_id_token)
            firebase_phone = decoded_token.get('phone_number')
            firebase_uid = decoded_token.get('uid')

            if not firebase_phone or firebase_phone != phone_number:
                audit_logger.warning(f"Phone number mismatch: {phone_number} vs {firebase_phone}")
                return Response({'error': 'Invalid phone number in Firebase token'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                otp_verification = OTPVerification.objects.select_related('user').get(
                    phone_number=phone_number, 
                    is_verified=False
                )
                
                # Check if OTP is expired (5 minutes)
                if otp_verification.created_at < timezone.now() - timedelta(minutes=5):
                    otp_verification.delete()
                    return Response(
                        {'error': 'OTP expired. Please request a new one.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                user = otp_verification.user
                if not user:
                    return Response(
                        {'error': 'User not found'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Update verification record
                otp_verification.is_verified = True
                otp_verification.verified_at = timezone.now()
                otp_verification.firebase_uid = firebase_uid
                otp_verification.save()

                # Update user
                user.is_phone_verified = True
                user.phone_number = phone_number
                user.save()

                refresh = RefreshToken.for_user(user)
                _store_refresh_token(user, refresh, request)

                response = Response({
                    'access_token': str(refresh.access_token), 
                    'user': UserSerializer(user).data, 
                    'message': 'Phone verification successful'
                })
                _set_refresh_cookie(response, refresh, request)

                create_audit_log(
                    user, 
                    'otp_verified', 
                    get_client_ip(request), 
                    request.META.get('HTTP_USER_AGENT', ''), 
                    {'phone_number': phone_number, 'firebase_uid': firebase_uid}
                )
                
                audit_logger.info(f"OTP verified successfully for {phone_number}")
                return response
                
            except OTPVerification.DoesNotExist:
                audit_logger.warning(f"OTP verification record not found for {phone_number}")
                return Response(
                    {'error': 'Invalid or expired OTP verification'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            audit_logger.error(f"Firebase token verification failed: {str(e)}")
            return Response(
                {'error': 'Invalid or expired Firebase token'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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