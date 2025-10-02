from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, mobile, name, role, **extra_fields):
        if not mobile: raise ValueError('Mobile number required')
        user = self.model(mobile=mobile, name=name, role=role, **extra_fields)
        user.set_unusable_password() 
        user.save()
        return user

    def create_superuser(self, mobile, name, password=None, **extra_fields):
        if not password:
            raise ValueError('Superuser must have a password')
        user = self.create_user(mobile, name, role='root_admin', **extra_fields)
        user.set_password(password)  # Set actual password instead of unusable
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return user

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('root_admin','Root Admin'),
        ('manager','Manager'),
        ('user','User'),
    ]
    mobile            = models.CharField(max_length=15, unique=True)
    name              = models.CharField(max_length=100,null=True, blank=True, default='empty')
    email             = models.EmailField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    role              = models.CharField(max_length=20, choices=ROLE_CHOICES)
    plan_type         = models.CharField(max_length=100, blank=True)
    trial_start       = models.DateTimeField(null=True, blank=True)
    trial_end         = models.DateTimeField(null=True, blank=True)
    default_tone      = models.ForeignKey('moderator_app.Tone', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_users')
    is_active         = models.BooleanField(default=True)
    is_staff          = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    def start_trial(self):
        if not self.trial_start:
            now = timezone.now()
            self.trial_start = now
            self.trial_end   = now + timedelta(days=14)
            self.save(update_fields=['trial_start', 'trial_end'])
            return True
        return False

    def __str__(self):
        return f"{self.name} ({self.mobile})"

class DailyUsage(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    usage_date = models.DateField(default=timezone.now)
    comment_used = models.PositiveBigIntegerField()
    photo_summaries_used = models.PositiveBigIntegerField()
    video_summaries_used = models.PositiveBigIntegerField()