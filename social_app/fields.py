import base64
import hashlib
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class EncryptedTextField(models.TextField):
    """Transparent Fernet encryption. Encrypted at rest, plaintext in Python."""

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode('utf-8')).decode('utf-8')
        except (InvalidToken, Exception):
            # Return as-is for any existing plaintext values during migration window
            return value

    def get_prep_value(self, value):
        if not value:
            return value
        return _get_fernet().encrypt(value.encode('utf-8')).decode('utf-8')
