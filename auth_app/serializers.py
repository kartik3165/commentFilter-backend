from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.conf import settings
from .models import User, OTPVerification
import requests
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

def verify_recaptcha_v3(token: str, *, expected_action: str, request=None) -> None:
    from django.conf import settings
    from rest_framework import serializers

    secret_key = getattr(settings, "RECAPTCHA_SECRET_KEY", None)
    if not secret_key:
        raise ImproperlyConfigured("RECAPTCHA_SECRET_KEY is not configured")

    # ✅ Google test secret key (always succeeds, no score/action/hostname)
    TEST_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
    if secret_key == TEST_SECRET_KEY:
        # Skip real verification in test mode
        return

    # ✅ Allow bypass in DEBUG mode too
    if getattr(settings, "DEBUG", False):
        return

    # Normal production flow
    min_score = getattr(settings, "RECAPTCHA_MIN_SCORE", 0.5)
    enforce_hostname = getattr(settings, "RECAPTCHA_ENFORCE_HOSTNAME", False)

    # Send user's IP to Google for better risk analysis
    remoteip = None
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        remoteip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR"))

    data = {
        "secret": secret_key,
        "response": token,
    }
    if remoteip:
        data["remoteip"] = remoteip

    try:
        import requests
        r = requests.post("https://www.google.com/recaptcha/api/siteverify", data=data, timeout=5)
        result = r.json()
    except Exception:
        raise serializers.ValidationError({"recaptcha_token": "reCAPTCHA verification service unavailable"})

    # Must be successful
    if not result.get("success", False):
        raise serializers.ValidationError({"recaptcha_token": "reCAPTCHA verification failed"})

    # v3-specific checks
    score = result.get("score", 0.0)
    action = result.get("action", "")
    hostname = result.get("hostname", "")

    if action != expected_action:
        raise serializers.ValidationError({"recaptcha_token": "Invalid reCAPTCHA action"})
    if score < float(min_score):
        raise serializers.ValidationError({"recaptcha_token": f"Low reCAPTCHA score ({score})"})
    if enforce_hostname:
        if request is not None:
            req_host = request.get_host().split(":")[0]
            if hostname != req_host:
                raise serializers.ValidationError({"recaptcha_token": "Hostname mismatch"})


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    recaptcha_token = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ("email", "username", "password", "password_confirm", "phone_number", "recaptcha_token")

    def validate(self, attrs):
        # Password match first
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match"})

        # Enforce reCAPTCHA v3 (action = "register")
        token = attrs.get("recaptcha_token")
        if not token:
            raise serializers.ValidationError({"recaptcha_token": "This field is required"})
        verify_recaptcha_v3(token, expected_action="register", request=self.context.get("request"))

        # Cleanup write_only fields
        attrs.pop("password_confirm", None)
        attrs.pop("recaptcha_token", None)
        return attrs

    def create(self, validated_data):
        phone_number = validated_data.pop("phone_number")
        user = User.objects.create_user(**validated_data)
        # Create OTP verification record
        OTPVerification.objects.create(user=user, phone_number=phone_number)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    recaptcha_token = serializers.CharField(write_only=True)  # <-- mandatory now

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        token = attrs.get("recaptcha_token")

        if not token:
            raise serializers.ValidationError({"recaptcha_token": "This field is required"})

        # Enforce reCAPTCHA v3 (action = "login") BEFORE auth to slow bots
        verify_recaptcha_v3(token, expected_action="login", request=self.context.get("request"))

        if not (email and password):
            raise serializers.ValidationError("Must provide email and password")

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if hasattr(user, "is_account_locked") and user.is_account_locked():
            raise serializers.ValidationError("Account is temporarily locked")

        attrs["user"] = user
        return attrs


class OTPVerificationSerializer(serializers.Serializer):
    firebase_id_token = serializers.CharField()
    phone_number = serializers.CharField()

    def validate_firebase_id_token(self, value):
        if not value:
            raise serializers.ValidationError("Firebase ID token is required")
        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "phone_number", "is_phone_verified", "is_email_verified")
        read_only_fields = ("id", "is_phone_verified", "is_email_verified")


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['is_phone_verified'] = user.is_phone_verified
        token['roles'] = list(user.groups.values_list('name', flat=True))
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        return token