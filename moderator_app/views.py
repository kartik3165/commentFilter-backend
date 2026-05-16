import hmac
import hashlib
import logging
from django.http import HttpResponse
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import redis
from rest_framework import status, views
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from social_app.models import Social_account
from subscription_app.models import Subscription
from moderator_app.tasks import generatePostSummaryChain, getCommentDecisionChain

User = get_user_model()
logger = logging.getLogger('auth')

r = redis.Redis.from_url(settings.REDIS_URL)

DAILY_TTL = 86400


def _verify_meta_signature(request) -> bool:
    if not settings.META_APP_SECRET:
        logger.warning("[webhook] META_APP_SECRET not configured — signature check skipped")
        return False
    sig_header = request.headers.get('X-Hub-Signature-256', '')
    if not sig_header.startswith('sha256='):
        return False
    expected = hmac.new(
        settings.META_APP_SECRET.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sig_header[7:], expected)


def _get_user_from_payload(payload) -> User:
    entries = payload.get('entry', [])
    if not entries:
        raise ValueError("No entry in webhook payload")
    platform_account_id = entries[0].get('id')
    if not platform_account_id:
        raise ValueError("No platform account ID in webhook payload")
    account = Social_account.objects.select_related('user_id').get(
        platform_account_id=platform_account_id,
        status=True
    )
    return account.user_id


@method_decorator(csrf_exempt, name='dispatch')
class Meta_WebhookView(views.APIView):
    authentication_classes = ()
    permission_classes = []

    def get(self, request, *args, **kwargs):
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if verify_token and verify_token == settings.META_VERIFICATION_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse("Invalid verification token", status=403)

    def post(self, request, *args, **kwargs):
        if not _verify_meta_signature(request):
            return Response({"error": "Invalid signature"}, status=403)

        payload = request.data
        try:
            for change in payload:
                media_id = change.get("data", {}).get("media_id")
                if media_id:
                    generatePostSummaryChain(media_id)
        except Exception as e:
            logger.error(f"[Meta_WebhookView] Error processing payload: {e}")
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "payload given to celery worker"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class Meta_CommentWebhookView(views.APIView):
    authentication_classes = ()
    permission_classes = []

    def get(self, request, *args, **kwargs):
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if verify_token and verify_token == settings.META_VERIFICATION_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse("Invalid verification token", status=403)

    def post(self, request, *args, **kwargs):
        if not _verify_meta_signature(request):
            return Response({"error": "Invalid signature"}, status=403)

        payload = request.data
        comment_list = []

        try:
            user = _get_user_from_payload(payload)
        except Social_account.DoesNotExist:
            logger.warning("[Meta_CommentWebhookView] No linked social account for webhook payload")
            return Response({"error": "No linked account found"}, status=404)
        except ValueError as e:
            logger.warning(f"[Meta_CommentWebhookView] Bad payload: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

        try:
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

                    # Idempotency — Meta retries on timeout
                    idempotency_key = f"webhook:processed:{comment_id}"
                    if cache.get(idempotency_key):
                        logger.info(f"[Meta_CommentWebhookView] Duplicate webhook for comment {comment_id}, skipping")
                        continue
                    cache.set(idempotency_key, True, timeout=DAILY_TTL)

                    count = int(r.hincrby(key, 'count', 1))
                    limit = int(r.hget(key, 'limit') or 0)

                    if count >= limit:
                        r.hincrby(key, 'count', -1)
                        cache.delete(idempotency_key)
                        return Response(
                            {'error': 'Daily comment limit reached'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS
                        )

                    logger.info(f'[Meta_CommentWebhookView] count={count}/{limit} key={key}')

                    comment_data = {
                        "comment_id": comment_id,
                        "parent_id": parent_id,
                        "post_id": post_id,
                        "text": text,
                        "username": username,
                    }
                    comment_list.append(comment_data)
                    getCommentDecisionChain(comment_data)

        except Exception as e:
            logger.error(f"[Meta_CommentWebhookView] Error: {e}")
            return Response(
                {"error": f"Invalid payload: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"message": "comment payload processed"}, status=status.HTTP_200_OK)
