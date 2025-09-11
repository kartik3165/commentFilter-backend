from rest_framework import serializers

class GetPostCaptionSerializer(serializers.Serializer):
    media_id = serializers.CharField(max_length = 200)


class PostInfoSerializers(serializers.Serializer):
    caption_original = serializers.CharField()
    media_url = serializers.JSONField()
    media_type = serializers.CharField()
    

