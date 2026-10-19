from auditlog.models import LogEntry
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from .serializers import AuditLogSerializer


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated
            and (getattr(u, 'role', '') == 'ADMIN' or u.is_superuser)
        )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LogEntry.objects.select_related('actor', 'content_type').order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]

    def list(self, request, *args, **kwargs):
        # latest 500 entries
        rows = self.filter_queryset(self.get_queryset())[:500]
        return Response(self.get_serializer(rows, many=True).data)