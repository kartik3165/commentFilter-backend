from .models import AuthAuditLog

def create_audit_log(user, event, ip_address, user_agent, details=None):
    AuthAuditLog.objects.create(
        user=user,
        event=event,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {}
    )

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip