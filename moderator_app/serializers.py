from rest_framework import serializers

class GetPostCaptionSerializer(serializers.Serializer):
    media_id = serializers.CharField(max_length=200)

class PostInfoSerializers(serializers.Serializer):
    caption_original = serializers.CharField(required=False, allow_blank=True)
    media_url = serializers.CharField(required=False, allow_blank=True)
    media_type = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(required=False)
    username = serializers.CharField(required=False, allow_blank=True) 
    timestamp = serializers.CharField(required=False)

class CommentSerializers(serializers.Serializer):
    platform_comment_id = serializers.CharField(required=False, allow_blank=True)
    parent_comment_id = serializers.CharField(required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(required=False, allow_blank=True)




