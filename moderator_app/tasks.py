from django.conf import settings
from social_app.models import Social_account
from moderator_app.serializers import PostInfoSerializers
from django.contrib.auth import get_user_model
import requests
from celery import shared_task, chain
from moderator_app.models import Post, Comment
from moderator_app.utils import extract_summary
from django.shortcuts import get_object_or_404

User = get_user_model()


import logging
logger = logging.getLogger('auth')

@shared_task(bind=True, max_retries=3, default_retry_delay=5, queue="webhook_post_queue")
def store_mediaIdTask(self, media_id):
    try:
        created, _= Post.objects.get_or_create(platform_post_id=media_id)
        logger.info(f"[store_mediaIdTask] Media {media_id} created: {created}")
        return media_id
    except Exception as e:
        logger.error(f"[store_mediaIdTask] Error: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=10, queue="webhook_post_queue")
def get_postInfoTask(self, media_id):
    try:
        response = requests.get('http://127.0.0.1:8002/api/post/')
        response.raise_for_status()
        data = response.json()
        logger.info(f"[get_postInfoTask] API Response: {data}")

        serializer_data = {
            'id': data.get('id', ''),
            'caption_original': data.get('caption', ''), 
            'media_url': data.get('media_url', ''),
            'media_type': data.get('media_type', ''),
            'username': data.get('owner', {}).get('username', ''), 
            'timestamp': data.get('timestamp', '')
        }

        serializer = PostInfoSerializers(data=serializer_data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                post = Post.objects.get(platform_post_id=media_id)
            except Post.DoesNotExist:
                logger.error(f"[get_postInfoTask] Post with media_id {media_id} not found")
                raise Exception(f"Post with media_id {media_id} not found")
            
            # Update post fields
            post.media_type = valid_data.get('media_type')
            post.media_url = valid_data.get('media_url')
            post.caption_original = valid_data.get('caption_original', '')

            # ✅ Prefer stable owner.id (Instagram user ID) over username
            owner_id = data.get('owner', {}).get('id')
            if owner_id:
                social_account = Social_account.objects.filter(
                    platform__name='instagram',
                    platform_account_id=owner_id
                ).first()

                if social_account:
                    post.user_id = social_account.user_id
                else:
                    logger.warning(f"[get_postInfoTask] No Social_account found for owner_id={owner_id}")
            else:
                logger.warning("[get_postInfoTask] No owner.id in payload, skipping user assignment")

            post.save()
            post.refresh_from_db()

            logger.info(f"[get_postInfoTask] Post updated successfully: {media_id}")
            return media_id
        else:
            logger.error(f"[get_postInfoTask] Serializer invalid: {serializer.errors}")
            logger.error(f"[get_postInfoTask] Raw data received: {data}")
            logger.error(f"[get_postInfoTask] Serializer data: {serializer_data}")
            raise Exception(f"Serializer validation failed: {serializer.errors}")
                
    except requests.RequestException as e:
        logger.error(f"[get_postInfoTask] Request Error: {e}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"[get_postInfoTask] Error: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=5, default_retry_delay=30, queue="webhook_post_queue")
def generate_summary(self, media_id):
    try:
        # Verify post exists and has required data
        try:
            post = Post.objects.get(platform_post_id=media_id)
            post.refresh_from_db()
        except Post.DoesNotExist:
            logger.error(f"[generate_summary] Post with media_id {media_id} not found")
            raise Exception(f"Post with media_id {media_id} not found")
        
        # Check if caption_original exists
        if not post.caption_original:
            logger.error(f"[generate_summary] Post {media_id} has no caption_original")
            raise Exception(f"Post {media_id} has no caption to summarize")
        
        # OpenRouter API configuration
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.SITE_URL if hasattr(settings, 'SITE_URL') else "http://localhost:8001",
            "X-Title": "Instagram Summary Generator"
        }
        
        payload = {
            "model": "nvidia/nemotron-nano-9b-v2:free", 
            "messages": [{
                "role": "user",
                "content": f'Summarize "{post.caption_original}" into exactly 8 words for a {post.media_type} on Instagram. Return only the eight word summary enclosed in curly brackets {{}}.'
            }],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        logger.info(f'[generate_summary] Generating summary for post {media_id}')
        
        # Call OpenRouter API
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"[generate_summary] OpenRouter API response: {data}")

        # Extract content from OpenRouter response
        if 'choices' not in data or not data['choices']:
            logger.warning(f"[generate_summary] No choices returned from API")
            raise self.retry(exc=Exception("No response from OpenRouter API"))
        
        content = data['choices'][0]['message']['content']
        
        if not content:
            logger.warning(f"[generate_summary] Empty content returned from API")
            raise self.retry(exc=Exception("Empty response from OpenRouter API"))
        
        # Extract summary from response (assuming it returns content in {} brackets)
        result = extract_summary(content)
        
        # Update post with summary
        post.caption_summary = result
        post.summary_generated = True
        post.save()
        
        logger.info(f"[generate_summary] Summary generated for {media_id}: {result}")
        return result

    except requests.RequestException as e:
        logger.error(f"[generate_summary] OpenRouter API Request Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"[generate_summary] Response status: {e.response.status_code}")
            logger.error(f"[generate_summary] Response content: {e.response.text}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"[generate_summary] Error: {e}")
        raise self.retry(exc=e)


def generatePostSummaryChain(media_id):
    workflow = chain(
        store_mediaIdTask.s(media_id), # type: ignore
        get_postInfoTask.s(), # type: ignore
        generate_summary.s() # type: ignore
    )
    logger.info(f"[generatePostSummaryChain] Workflow started for: {media_id}")
    workflow.apply_async() # remove apply_async latter 


@shared_task(bind=True, max_retries=3, default_retry_delay=5, queue='meta_comment_info_queue')
def store_commentIdTask(self, comment_id):
    try:
        created, _ = Comment.objects.get_or_create(platform_comment_id = comment_id)
        logger.info(f'comment added {comment_id}')
        return comment_id
    except Exception as e:
        logger.error(f'store_comment_id Error: {e}')
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=5, queue='meta_comment_info_queue')
def get_commentInfoTask(self,comment_id):
    try:
        response = requests.get('http://127.0.0.1:8002/api/comment/')
    except:
        pass

def getCommentDecisionChain(comment_id):
    workflow = chain(
        store_commentIdTask.s(comment_id),
    )

    workflow.apply_async()




