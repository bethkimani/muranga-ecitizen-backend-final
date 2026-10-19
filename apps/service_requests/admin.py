from django.contrib import admin
from .models import ServiceRequest, RequestEvidence, TimelineEvent


class EvidenceInline(admin.TabularInline):
    model = RequestEvidence
    extra = 0


class TimelineInline(admin.TabularInline):
    model = TimelineEvent
    extra = 0


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('ref_number', 'title', 'category', 'status', 'ward', 'submitted_at')
    list_filter = ('status', 'category', 'sub_county')
    search_fields = ('ref_number', 'title', 'ward')
    inlines = [EvidenceInline, TimelineInline]