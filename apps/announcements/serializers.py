from rest_framework import serializers
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    summary = serializers.CharField(source='body', read_only=True)
    published_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'summary', 'category', 'published_at']