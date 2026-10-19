from rest_framework import serializers
from apps.service_requests.models import ServiceRequest, RequestEvidence, TimelineEvent
from apps.categories.serializers import CategorySerializer

class RequestEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestEvidence
        fields = ['id', 'image_url', 'uploaded_at']

class TimelineEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimelineEvent
        fields = ['id', 'title', 'body', 'author_name', 'kind', 'created_at']

class ServiceRequestSerializer(serializers.ModelSerializer):
    evidence = RequestEvidenceSerializer(many=True, read_only=True)
    timeline = TimelineEventSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'ref_number', 'title', 'description', 'category', 'citizen',
            'sub_county', 'ward', 'landmark', 'coordinates', 'status',
            'assigned_department', 'assigned_officer', 'status_note',
            'evidence', 'timeline', 'submitted_at', 'updated_at'
        ]
        read_only_fields = ['ref_number', 'citizen', 'status', 'submitted_at', 'updated_at']