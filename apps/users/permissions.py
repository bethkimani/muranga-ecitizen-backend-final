from rest_framework.permissions import BasePermission

STAFF_ROLES = ('STAFF', 'DEPT_HEAD', 'ADMIN')


def effective_role(user):
    if not user or not user.is_authenticated:
        return None
    return 'ADMIN' if user.is_superuser else user.role


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return effective_role(request.user) == 'ADMIN'


class IsStaffRole(BasePermission):
    def has_permission(self, request, view):
        return effective_role(request.user) in STAFF_ROLES


class IsDeptHeadOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return effective_role(request.user) in ('DEPT_HEAD', 'ADMIN')