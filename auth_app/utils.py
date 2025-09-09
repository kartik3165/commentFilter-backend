# utils.py
import random
import hashlib
from django.core.cache import cache
from django.conf import settings
from twilio.rest import Client

OTP_TTL = 300 

def _hash_otp(mobile, otp):
    return hashlib.sha256(f"{mobile}:{otp}".encode()).hexdigest()

def send_otp(mobile):
    otp = str(random.randint(100000, 999999))
    hashed = _hash_otp(mobile, otp)
    cache.set(f"otp:{mobile}", hashed, OTP_TTL)
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=f"Your OTP is {otp}",
        from_=settings.TWILIO_FROM_NUMBER,
        to=mobile
    )
    return True

def verify_otp(mobile, otp):
    hashed = cache.get(f"otp:{mobile}")
    if not hashed:
        return False
    return hashed == _hash_otp(mobile, otp)

