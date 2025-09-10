from django.shortcuts import render
from django.http import JsonResponse
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

User = get_user_model()
# Create your views here.
class Get_post_caption(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    serializer = GetPostCaptionSerializer(data = )