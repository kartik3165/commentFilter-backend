from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AuthAuditLog, OTPVerification, UserRefreshToken

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'phone_number', 'is_email_verified', 
                   'is_phone_verified', 'is_account_locked', 'failed_login_attempts', 
                   'created_at', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_email_verified', 'is_phone_verified', 
                  'created_at', 'updated_at')
    search_fields = ('email', 'username', 'phone_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Verification', {
            'fields': ('is_email_verified', 'is_phone_verified')
        }),
        ('Security', {
            'fields': ('failed_login_attempts', 'account_locked_until')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 
                      'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'created_at', 'updated_at')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2')}
        ),
    )
    
    def is_account_locked(self, obj):
        return obj.is_account_locked()
    is_account_locked.boolean = True
    is_account_locked.short_description = 'Locked'

@admin.register(AuthAuditLog)
class AuthAuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'ip_address', 'timestamp', 'short_user_agent')
    list_filter = ('event', 'timestamp')
    search_fields = ('user__email', 'user__username', 'ip_address')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    def short_user_agent(self, obj):
        return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
    short_user_agent.short_description = 'User Agent' # type: ignore

class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'firebase_uid', 'is_verified', 'created_at', 'verified_at')
    list_filter = ('is_verified', 'created_at', 'verified_at')
    search_fields = ('user__email', 'user__username', 'phone_number', 'firebase_uid')
    readonly_fields = ('created_at',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('user')

admin.site.register(OTPVerification, OTPVerificationAdmin)


@admin.register(UserRefreshToken)
class UserRefreshTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'device_info', 'created_at', 'token_short')
    list_filter = ('created_at', 'device_info', 'user')
    search_fields = ('user__email', 'device_info', 'token')
    ordering = ('-created_at',)

    def token_short(self, obj):
        # Show only first 20 chars of token for readability
        return obj.token[:20] + "..."
    token_short.short_description = "Refresh Token"