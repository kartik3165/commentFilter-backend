# views.py

from django.http import JsonResponse
from rest_framework import status, permissions, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from django.conf import settings
from django.utils import timezone

from moderator_app.models import Tone, ToneSetting
from .serializers import SendOTPSerializer, TrialSerializer, VerifyOTPSerializer, UserSerializer, ProfileInfoSerializer
from .utils import send_otp, verify_otp

User = get_user_model()



class VerifyOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            mobile = serializer.validated_data['mobile']
            otp = serializer.validated_data['otp']

            if not verify_otp(mobile, otp):
                return Response({
                    "detail": "Invalid or expired OTP."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get or create user
            user, created = User.objects.get_or_create(
                mobile=mobile,
                defaults={'role': 'user'},
            )

            master_tone = Tone.objects.get(name='Default')
            user_tone = Tone.objects.create(
                name=f'{user.mobile} Default',
                created_by = user
            )

            master_settings = ToneSetting.objects.filter(tone = master_tone)
            for setting in master_settings:
                ToneSetting.objects.create(
                    tone=user_tone,
                    tone_type=setting.tone_type,
                    enabled=setting.enabled
                )

            user.default_tone = user_tone

            needs_profile_completion = user.name == 'empty'

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)


            response = Response({
                'access': access_token,
                'user': UserSerializer(user).data,
                'needs_profile_completion': needs_profile_completion
            }, status=status.HTTP_200_OK)

            # Set refresh token in HttpOnly cookie
            response.set_cookie(
                key='refresh_token',
                value=str(refresh),
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=7 * 24 * 60 * 60,  # 7 days
                path='/'
            )

            return response
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileInfoView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        serializer = ProfileInfoSerializer(
            instance=request.user,
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile updated successfully",
                "user": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(views.APIView):
    def post(self, request):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            response = Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
            response.delete_cookie('refresh_token', path='/')
            return response
        except Exception as e:
            response = Response({"detail": "Logout failed"}, status=status.HTTP_400_BAD_REQUEST)
            response.delete_cookie('refresh_token', path='/')
            return response

class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        
        if not refresh_token:
            return Response({
                "detail": "Refresh token not found in cookies"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        request.data['refresh'] = refresh_token
        
        try:
            response = super().post(request, *args, **kwargs)

            if hasattr(settings, 'SIMPLE_JWT') and settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                if 'refresh' in response.data:
                    response.set_cookie(
                        key='refresh_token',
                        value=response.data['refresh'],
                        httponly=True,
                        secure=not settings.DEBUG,
                        samesite='Lax',
                        max_age=7 * 24 * 60 * 60,  
                        path='/'
                    )
            
            return response
            
        except Exception as e:
            return Response({
                "detail": f"Token refresh failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)

class SendOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    
    @method_decorator(ratelimit(key='post:mobile', rate='3/10m', method='POST'))
    @method_decorator(ratelimit(key='ip', rate='10/h', method='POST'))
    def post(self, request):
        if getattr(request, 'limited', False):
            return Response({
                "detail": "Too many OTP requests. Please try again later."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            try:
                mobile = serializer.validated_data['mobile']
                send_otp(mobile)
                return Response({
                    "detail": "OTP sent successfully"
                }, status=status.HTTP_200_OK)
                
            except AttributeError as e:
                return Response({
                    "detail": f"Server configuration error: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            except Exception as e:
                return Response({
                    "detail": f"Failed to send OTP: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class CurrentUserView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data) 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_trial_view(request):
    user = request.user
    if user.start_trial():
        serializer = TrialSerializer(user)
        return Response({
            "message": "Trial started successfully!",
            "data": serializer.data
        }, status=200)
    else:
        serializer = TrialSerializer(user)
        return Response({
            "message": "Trial already started.",
            "data": serializer.data
        }, status=400)