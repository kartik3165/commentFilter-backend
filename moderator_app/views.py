from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from rest_framework import status, permissions, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from django.conf import settings
from django.utils import timezone

from moderator_app.serializers import GetPostCaptionSerializer
from moderator_app.tasks import generatePostSummaryChain, getCommentDecisionChain

User = get_user_model()

class Meta_WebhookView(views.APIView):
    authentication_classes = () 
    # permission_classes = [IsAuthenticated] commentout in production

    def get(self, request, *args, **kwargs):
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if verify_token == settings.META_VERIFICATION_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse("Invalid verification token", status=403)
    
    def post(self, request, *args, **kwargs):
        payload = request.data
        try:
            for change in payload:
                media_id = change.get("data", {}).get("media_id")
                if media_id:
                    generatePostSummaryChain(media_id) 
        except Exception as e:
            return Response(
                {"error": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
                {"message": "payload given to celery worker"},
                status=status.HTTP_200_OK
            )

class Meta_CommentWebhookView(views.APIView):
    authentication_classes = () 
    # permission_classes = [IsAuthenticated]  # enable in production

    def get(self, request, *args, **kwargs):
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if verify_token == settings.META_VERIFICATION_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse("Invalid verification token", status=403)

    def post(self, request, *args, **kwargs):
        payload = request.data
        comment_list = []
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "comments":
                        value = change.get("value", {})
                        comment_id = value.get("id")
                        if comment_id:
                            comment_list.append(comment_id)
                            getCommentDecisionChain.delay(comment_id) # type: ignore
                        
                        # parent_id = value.get("parent_id") 
                        # post_id = value.get("media", {}).get("id")
                        # text = value.get("text")
                        # username = value.get("username")

        except Exception as e:
            return Response(
                {"error": f"Invalid payload: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "message": "comment payload processed",
                'process_comment' : f'{comment_list}'
            },
            status=status.HTTP_200_OK
        )




