from auditlog.models import LogEntry
from rest_framework import serializers


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    action_label = serializers.CharField(source='get_action_display', read_only=True)
    model = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()

    class Meta:
        model = LogEntry
        fields = [
            'id', 'timestamp', 'actor_name', 'action', 'action_label',
            'model', 'object_repr', 'changes', 'remote_addr',
        ]

    def get_actor_name(self, obj):
        a = obj.actor
        if not a:
            return 'System'
        full = a.get_full_name() if hasattr(a, 'get_full_name') else ''
        return full or getattr(a, 'email', '') or getattr(a, 'username', '') or str(a)

    def get_model(self, obj):
        return obj.content_type.model if obj.content_type else ''

    def get_changes(self, obj):
        data = getattr(obj, 'changes_dict', None)
        return data if isinstance(data, dict) else {}