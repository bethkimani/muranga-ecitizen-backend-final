from rest_framework import viewsets, permissions
from .models import Department, Category
from .serializers import DepartmentSerializer, CategorySerializer


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.AllowAny]


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.select_related('department').all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]