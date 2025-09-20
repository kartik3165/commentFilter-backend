import logging
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import redis
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
from django.shortcuts import get_object_or_404

from moderator_app.serializers import GetPostCaptionSerializer
from subscription_app.models import Plan, Subscription
from moderator_app.tasks import generatePostSummaryChain, getCommentDecisionChain


User = get_user_model()

logger = logging.getLogger('auth')

r = redis.Redis.from_url(settings.REDIS_URL)
 
DAILY_TTL= 86400

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

    # def post(self, request, *args, **kwargs):
    #     payload = request.data
    #     comment_list = []
    #     try:
    #         for entry in payload.get("entry", []):
    #             for change in entry.get("changes", []):
    #                 if change.get("field") == "comments":
    #                     value = change.get("value", {})
    #                     comment_id = value.get("id")
    #                     parent_id = value.get("parent_id") 
    #                     post_id = value.get("media", {}).get("id")
    #                     text = value.get("text")
    #                     username = value.get("username")
    #                     if comment_id:
    #                         # user_id = getattr(request.user, 'id', None) # for production 
    #                         ## for testing 
    #                         user= User.objects.get(mobile = 7894561230)
    #                         if not user:
    #                             return Response({"error": "User not authenticated"}, status=403)
    #                         try:
    #                             subscription = Subscription.objects.get(user_id=user)
    #                         except Subscription.DoesNotExist:
    #                             return Response({"error": "No active subscription for this user"}, status=400)
    #                         today = timezone.now().date()
    #                         key = f'{User}:comments{today}'
    #                         if not r.exists(key):
    #                             subscription = Subscription.objects.get(user_id = user)
    #                             r.hset(key, mapping={'count': 0, 'limits': subscription.plan_id.comment_limit})
    #                             r.expire(key, DAILY_TTL)
                            
    #                         count = r.hincrby(key,'count', 1)
    #                         limit = int(r.hget(key, 'limit'))

    #                         if count > limit:
    #                             r.hincrby(key, 'count', -1)
    #                             return Response(
    #                                 {'error': 'Comment limit reached'},
    #                                 status=status.HTTP_403_FORBIDDEN
    #                             )
                            
    #                         logger.warning(f'limiting count : {key} limit : {limit} key : {key}')
    #                         comment_data = {
    #                                     "comment_id": comment_id,
    #                                     "parent_id": parent_id,
    #                                     "post_id": post_id,
    #                                     "text": text,
    #                                     "username": username,
    #                                 }
    #                         comment_list.append(comment_data)
    #                         getCommentDecisionChain(comment_data) # type: ignore
                        
    #                     parent_id = value.get("parent_id") 
    #                     post_id = value.get("media", {}).get("id")
    #                     text = value.get("text")
    #                     username = value.get("username")

    #     except Exception as e:
    #         return Response(
    #             {"error": f"Invalid payload: {str(e)}"},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     return Response(
    #         {
    #             "message": "comment payload processed",
    #         },
    #         status=status.HTTP_200_OK
    #     )


    # from uuid import UUID

    def post(self, request, *args, **kwargs):
        payload = request.data
        comment_list = []
        try:
            # Hardcoded test user
            user = User.objects.get(mobile="7894561230")
            try:
                subscription = Subscription.objects.get(user_id=user)
            except Subscription.DoesNotExist:
                return Response({"error": "No active subscription for this user"}, status=400)

            today = timezone.now().date()
            key = f'user:{user.id}:comments:{today}'

            if not r.exists(key):
                r.hset(key, mapping={
                    'count': 0,
                    'limit': subscription.plan_id.comment_limit or 0
                })
                r.expire(key, DAILY_TTL)

            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") != "comments":
                        continue

                    value = change.get("value", {})
                    comment_id = value.get("id")
                    parent_id = value.get("parent_id")
                    post_id = value.get("media", {}).get("id")
                    text = value.get("text")
                    username = value.get("username")

                    if not comment_id:
                        continue

                    # Increment count
                    count = r.hincrby(key, 'count', 1)
                    limit = int(r.hget(key, 'limit'))

                    if count > limit:
                        r.hincrby(key, 'count', -1)
                        return Response(
                            {'error': 'Comment limit reached'},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    logger.warning(f'Limiting count: {count} / {limit} for key {key}')

                    comment_data = {
                        "comment_id": comment_id,
                        "parent_id": parent_id,
                        "post_id": post_id,
                        "text": text,
                        "username": username,
                    }
                    comment_list.append(comment_data)
                    getCommentDecisionChain(comment_data)  # type: ignore

        except Exception as e:
            return Response(
                {"error": f"Invalid payload: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "comment payload processed"},
            status=status.HTTP_200_OK
        )

