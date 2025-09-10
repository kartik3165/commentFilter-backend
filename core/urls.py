from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('auth_app.urls')),
    path('api/social/', include('social_app.urls')),
    path('api/moderator/', include('moderator_app.urls')),
    path('api/admin_app/', include('admin_app.urls'))
]
