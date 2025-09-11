from backend.moderator_app.serializers import PostInfoSerializers

import requests
from celery import shared_task, chain
from django.db import IntegrityError
from moderator_app.models import Post, Comment
from django.shortcuts import get_object_or_404



@shared_task(
        bind=True,
        max_retries=3,
        default_retry_delay=10,
        queue="webhook_post_queue"
        )
def store_mediaIdTask(self, media_id):
    try:
        created = Post.objects.get_or_create(platform_post_id=media_id)
        if created:
            return f"Media {media_id} created"
        else:
            return f"Media {media_id} already exists"
    except Exception as e:
        raise self.retry(exc=e)
    

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue="webhook_post_queue" # change queue
    # add rate limiting 
)
def get_postInfoTask(self,media_id):
    try:
        response = requests.get(f'https://graph.facebook.com/v21.0/{media_id}/comments?access_token=token') # change access token in production

        response.raise_for_status()
        data = response.json()

        serializer = PostInfoSerializers(data=data)
        if serializer.is_valid():
            valid_data = serializer.validated_data

            post = get_object_or_404(platform_post_id = media_id) # type: ignore

            post.media_type       = valid_data.get('media_type')
            post.media_url        = valid_data.get('media_url')
            post.caption_original = valid_data.get('caption_original')
            post.platform         = 'Instagram'
            post.save()

    except requests.RequestException as e:
        raise self.retry(exc= e)
    except Exception as e:
        raise self.retry(exc=e)
    


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue="webhook_post_queue" # change queue
    # add rate limiting 
)
def get_postInfoTask(self,media_id):      

    

