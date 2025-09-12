from django.urls import path

from moderator_app.views import Meta_WebhookView

urlpatterns = [
    path("webhook/meta/", Meta_WebhookView.as_view(), name="meta-webhook"),

]
