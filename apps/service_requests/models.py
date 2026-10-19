import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.categories.models import Category, Department


class RequestStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    IN_PROGRESS = 'In Progress', 'In Progress'
    RESOLVED = 'Resolved', 'Resolved'
    REJECTED = 'Rejected', 'Rejected'


class ServiceRequest(models.Model):
    ref_number = models.CharField(max_length=30, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='citizen_requests'
    )

    sub_county = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    landmark = models.CharField(max_length=255)
    coordinates = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(
        max_length=20, choices=RequestStatus.choices, default=RequestStatus.PENDING
    )
    assigned_department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cases',
    )
    status_note = models.TextField(blank=True, null=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Generate a unique reference number the first time the request is saved
        if not self.ref_number:
            for _ in range(10):
                ref = f"MUR-{timezone.now():%Y}-{secrets.token_hex(3).upper()}"
                if not ServiceRequest.objects.filter(ref_number=ref).exists():
                    self.ref_number = ref
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ref_number} - {self.title}"


class RequestEvidence(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='evidence')
    image_url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)


class TimelineEvent(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='timeline')
    title = models.CharField(max_length=200)
    body = models.TextField()
    author_name = models.CharField(max_length=150)
    kind = models.CharField(
        max_length=50,
        choices=[
            ('submitted', 'Submitted'),
            ('status', 'Status Update'),
            ('citizen', 'Citizen Follow-up'),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)