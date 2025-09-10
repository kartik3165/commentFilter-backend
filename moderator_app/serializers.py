from rest_framework import serializers

class GetPostCaptionSerializer(serializers.Serializer):
    class Meta:
    media_id = serializers.CharField(max_length = 150)

        model = Media
        fields = ['media_id']
