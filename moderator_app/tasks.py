from moderator_app.serializers import PostInfoSerializers

import ollama
from django.contrib.auth import get_user_model
import requests
from celery import shared_task, chain
from django.db import IntegrityError
from moderator_app.models import Post, Comment
from moderator_app.utils import extract_summary
from django.shortcuts import get_object_or_404

User = get_user_model()



# @shared_task(
#         bind=True,
#         max_retries=3,
#         default_retry_delay=5,
#         queue="webhook_post_queue"
#         )
# def store_mediaIdTask(self, media_id):
#     try:
#         created = Post.objects.get_or_create(platform_post_id=media_id)
#         if created:
#             return media_id
#         else:
#             return f"Media {media_id} already exists"
#     except Exception as e:
#         raise self.retry(exc=e)
    

# @shared_task(
#     bind=True,
#     max_retries=3,
#     default_retry_delay=10,
#     queue="webhook_post_queue" # change queue
#     # add rate limiting 
# )
# def get_postInfoTask(self, media_id):
#     try:
#         # for production
#         # response = requests.get(f'https://graph.facebook.com/v21.0/{media_id}/comments?access_token=token') # change access token in production
        
#         # for testing
#         response = requests.get(f'http://127.0.0.1:8002/api/post/') # change access token in production
        
#         response.raise_for_status()
#         data = response.json()

#         serializer = PostInfoSerializers(data=data)
#         if serializer.is_valid():
#             valid_data = serializer.validated_data

#             post = get_object_or_404(platform_post_id = media_id) # type: ignore

#             post.media_type       = valid_data.get('media_type')
#             post.media_url        = valid_data.get('media_url')
#             post.caption_original = valid_data.get('caption_original')
#             post.platform         = 'Instagram'
#             print(f"[DEBUG] Saving Post:\n media_type={post.media_type},\n "f"media_url={post.media_url},\n caption_original={post.caption_original},\n "f"platform={post.platform}\n")
#             post.save()

#             return media_id

#     except requests.RequestException as e:
#         print('--->Retrying')
#         raise self.retry(exc= e)
#     except Exception as e:
#         print('--->Retrying')
#         raise self.retry(exc=e)
    
    


# @shared_task(
#     bind=True,
#     max_retries=3,
#     default_retry_delay=10,
#     queue="webhook_post_queue" # change queue
#     # add rate limiting 
# )
# def generate_Summary(self,media_id): 
#     try:
#         post = get_object_or_404(Post, platform_post_id = media_id)

#         url = "http://localhost:11434/api/chat"
#         payload = {
#             'model' : 'llama3.2:latest',
#             'content' : [{
#                 'role': 'user',
#                 'content' : f'Summarize "{post.caption_original}" into exactly 8 words for a {post.media_type} on {post.platform}.' 
#                 'Return only eight word summary with this {} bracket.'

#             }],
#             'stream' : False
#         }
#         response = requests.post(url, json=payload)
#         response.raise_for_status()
#         data = response.json()
#         content = data["message"]["content"]
#         result = extract_summary(content)
#         post.caption_summary = result
#         post.summary_generated = True
#         post.save()
#         return result
    
#     except requests.RequestException as e:
#         raise self.retry(exc= e)
#     except Exception as e:
#         return self.retry(exc=e)


# def generatePostSummaryChain(media_id):
#     workflow = chain(
#         store_mediaIdTask.s(media_id),  
#         get_postInfoTask.s(),     
#         generate_Summary.s(),      
#     )
#     workflow()

import logging
logger = logging.getLogger('auth')

@shared_task(bind=True, max_retries=3, default_retry_delay=5, queue="webhook_post_queue")
def store_mediaIdTask(self, media_id):
    try:
        created, _ = Post.objects.get_or_create(platform_post_id=media_id)
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
        
        # Create serializer data mapping
        serializer_data = {
            'caption_original': data.get('caption', ''),  # Map 'caption' to 'caption_original'
            'media_url': data.get('media_url', ''),
            'media_type': data.get('media_type', '')
        }
        serializer = PostInfoSerializers(data=serializer_data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                post = Post.objects.get(platform_post_id=media_id)
            except Post.DoesNotExist:
                logger.error(f"[get_postInfoTask] Post with media_id {media_id} not found")
                raise Exception(f"Post with media_id {media_id} not found")
            
            post.media_type = valid_data.get('media_type')
            post.media_url = valid_data.get('media_url')
            post.caption_original = valid_data.get('caption_original', '')
            post.user_id = User
            # post.platform = platform_instance
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


@shared_task(bind=True, max_retries=3, default_retry_delay=10, queue="webhook_post_queue")
def generate_Summary(self, media_id):
    try:
        # Verify post exists and has required data
        try:
            post = Post.objects.get(platform_post_id=media_id)
            post.refresh_from_db()
        except Post.DoesNotExist:
            logger.error(f"[generate_Summary] Post with media_id {media_id} not found")
            raise Exception(f"Post with media_id {media_id} not found")
        
        # Check if caption_original exists
        if not post.caption_original:
            logger.error(f"[generate_Summary] Post {media_id} has no caption_original")
            raise Exception(f"Post {media_id} has no caption to summarize")
        
        payload = {
            'model': 'llama3.2:latest',
            'messages': [{  # Changed from 'content' to 'messages'
                'role': 'user',
                'content': f'Summarize "{post.caption_original}" into exactly 8 words for a {post.media_type} on Instagram. Return only eight word summary with this {{}} bracket.'
            }],
            'stream': False
        }
        
        response = requests.post("http://localhost:11434/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract summary from response
        content = data["message"]["content"]
        result = extract_summary(content)
        
        # Update post with summary
        post.caption_summary = result
        post.summary_generated = True
        post.save()
        
        logger.info(f"[generate_Summary] Summary generated for {media_id}: {result}")
        return result
        
    except requests.RequestException as e:
        logger.error(f"[generate_Summary] Request Error: {e}")
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"[generate_Summary] Error: {e}")
        raise self.retry(exc=e)



def generatePostSummaryChain(media_id):
    workflow = chain(
        store_mediaIdTask.s(media_id),
        get_postInfoTask.s(),
        generate_Summary.s()
    )
    logger.info(f"[generatePostSummaryChain] Workflow started for: {media_id}")
    workflow.apply_async() # remove apply_async latter 





