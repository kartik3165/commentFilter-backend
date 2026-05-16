import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from social_app.fields import EncryptedTextField
from admin_app.models import Platform

User = get_user_model()

class Social_account(models.Model):
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id             = models.ForeignKey( User, on_delete=models.CASCADE, related_name='social_accounts')
    platform            = models.ForeignKey(Platform, on_delete=models.CASCADE)
    platform_account_id = models.CharField(max_length=100)
    username            = models.CharField(max_length=150, null=True, blank=True)
    access_token        = EncryptedTextField()
    status              = models.BooleanField(default=True)
    linked_at           = models.DateTimeField(auto_now_add=True)
    unlinked_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'platform_account_id'],
                name='unique_user_platform'
            )
        ]
        ordering = ['-linked_at'] 

    def unlink(self):
        self.status = False
        self.unlinked_at = timezone.now()
        self.save(update_fields=['status', 'unlinked_at'])