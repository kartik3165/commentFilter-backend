from rest_framework import serializers

class GetPostCaptionSerializer(serializers.Serializer):
    media_id = serializers.CharField(max_length=200)

class PostInfoSerializers(serializers.Serializer):
    # Make all fields optional since we'll handle the mapping in the task
    caption_original = serializers.CharField(required=False, allow_blank=True)
    media_url = serializers.CharField(required=False, allow_blank=True)  # Changed from JSONField to CharField based on API response
    media_type = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(required=False)  # API returns 'id' field
    username = serializers.CharField(required=False)  # API returns 'username' field  
    timestamp = serializers.CharField(required=False)  # API returns 'timestamp' field



