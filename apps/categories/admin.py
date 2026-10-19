from django.contrib import admin
from .models import Department, Category


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'head_officer_name')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'response_target_days')
    list_filter = ('department',)
    search_fields = ('name',)