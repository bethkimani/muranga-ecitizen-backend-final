from django.contrib import admin
from apps.notifications.models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'read', 'created_at')
    list_filter = ('read', 'created_at')
    search_fields = ('user__phone_number', 'title', 'message')