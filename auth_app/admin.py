from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('mobile', 'name', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make password fields optional for regular users, required for superusers
        self.fields['password1'].required = False
        self.fields['password2'].required = False

    def save(self, commit=True):
        user = super().save(commit=False)
        # If no password provided, set unusable password (for passwordless login)
        if not self.cleaned_data.get('password1'):
            user.set_unusable_password()
        else:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove password requirement from change form
        if 'password' in self.fields:
            self.fields['password'].help_text = (
                "Raw passwords are not stored, so there is no way to see this "
                "user's password, but you can change the password using "
                "<a href=\"../password/\">this form</a>."
            )

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    
    list_display = ('mobile', 'name', 'role','is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active', 'plan_type')
    fieldsets = (
        (None, {'fields': ('mobile', 'name', 'password')}),
        ('Personal Info', {'fields': ('plan_type', 'email')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('mobile', 'name', 'role', 'plan_type', 'password1', 'password2', 'is_active', 'is_staff')}
        ),
    )
    
    search_fields = ('mobile', 'name', 'plan_type')
    ordering = ('mobile',)
    readonly_fields = ('created_at', 'updated_at', 'last_login')
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.has_usable_password() == False:
            if 'password' in form.base_fields:
                form.base_fields['password'].widget = form.base_fields['password'].hidden_widget()
        return form

admin.site.site_header = "Your App Administration"
admin.site.site_title = "Your App Admin"
admin.site.index_title = "Welcome to Your App Administration"