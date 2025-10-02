from django.urls import path

from moderator_app.views import Meta_WebhookView, Meta_CommentWebhookView

urlpatterns = [
    path("post-webhook/meta/", Meta_WebhookView.as_view(), name="post-webhook"),
    path("comment-webhook/meta/", Meta_CommentWebhookView.as_view(), name="comment-webhook")

]
