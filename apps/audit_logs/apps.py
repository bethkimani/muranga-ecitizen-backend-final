from django.apps import AppConfig


class AuditLogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit_logs'

    def ready(self):
        from auditlog.registry import auditlog
        from apps.service_requests.models import ServiceRequest
        from apps.announcements.models import Announcement
        from apps.categories.models import Category, Department

        for model in (ServiceRequest, Announcement, Category, Department):
            auditlog.register(model)