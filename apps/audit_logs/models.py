from auditlog.registry import auditlog
from apps.service_requests.models import ServiceRequest  # Fixed import
from apps.users.models import User

# Register models to track immutable audit logs for staff and admin actions
auditlog.register(ServiceRequest)
auditlog.register(User)