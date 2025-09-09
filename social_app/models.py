import uuid
from django.db import models
from auth_app.models import User
from django.utils import timezone

class Social_account(models.Model):
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id             = models.ForeignKey( User, on_delete=models.CASCADE, related_name='social_accounts')
    platform            = models.CharField(max_length=50, choices=PLATFORM_CHOICES, default='instagram')
    platform_account_id = models.CharField(max_length=100)
    access_token        = models.CharField(max_length=200)
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