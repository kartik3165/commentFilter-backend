from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

User = get_user_model()

class SendOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    
    def validate_mobile(self, value):
        if not value.startswith('+'):
            raise serializers.ValidationError("Mobile number must include country code (e.g., +91834567890)")
        return value

class VerifyOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6, min_length=6)
    
    def validate_mobile(self, value):
        if not value.startswith('+'):
            raise serializers.ValidationError("Mobile number must include country code")
        return value

class ProfileInfoSerializer(serializers.Serializer):
    name = serializers.CharField(
        required=True,
        min_length=2,
        max_length=50,
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z ]+$',
                message="Name can only contain letters and spaces"
            )
        ]
    )

    email = serializers.EmailField(
        required=True,
        max_length=100
    )

    class Meta:
        model = User
        fields = ['name', 'email']

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value
    
    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.email = validated_data.get('email', instance.email)
        instance.save()
        return instance

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','mobile','name','role', 'email']

class TrialSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['trial_start', 'trial_end']