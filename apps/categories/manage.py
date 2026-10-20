"""
Admin-only endpoints to add and edit departments and categories from the frontend.

  GET/POST   /api/manage/departments/        list, create
  GET/PATCH  /api/manage/departments/<id>/   read, edit
  GET/POST   /api/manage/categories/         list, create
  GET/PATCH  /api/manage/categories/<id>/    read, edit

The existing read-only /api/departments/ and /api/categories/ endpoints are untouched.
There is no delete on purpose: departments and categories are referenced by requests.
"""
from rest_framework import permissions, serializers, viewsets
from rest_framework.routers import DefaultRouter

from .models import Category, Department


class IsCountyAdmin(permissions.BasePermission):
    """Only signed-in users whose role is ADMIN."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'role', None) == 'ADMIN')


class DepartmentManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'head_officer_name']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter a department name.')
        duplicates = Department.objects.filter(name__iexact=value)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError('A department with this name already exists.')
        return value


class CategoryManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'department', 'description', 'response_target_days', 'icon_name']
        extra_kwargs = {'icon_name': {'required': False}}

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter a category name.')
        return value

    def validate_response_target_days(self, value):
        if value < 1:
            raise serializers.ValidationError('Response target must be at least 1 day.')
        return value

    def validate(self, attrs):
        name = attrs.get('name', getattr(self.instance, 'name', None))
        department = attrs.get('department', getattr(self.instance, 'department', None))
        if name and department:
            duplicates = Category.objects.filter(name__iexact=name, department=department)
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {'name': 'This department already has a category with this name.'}
                )
        return attrs


class DepartmentManageViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by('name')
    serializer_class = DepartmentManageSerializer
    permission_classes = [IsCountyAdmin]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class CategoryManageViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('department').order_by('department__name', 'name')
    serializer_class = CategoryManageSerializer
    permission_classes = [IsCountyAdmin]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


router = DefaultRouter()
router.register('departments', DepartmentManageViewSet, basename='manage-department')
router.register('categories', CategoryManageViewSet, basename='manage-category')

urlpatterns = router.urls