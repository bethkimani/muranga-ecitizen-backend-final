from django.db import models


class Announcement(models.Model):
    title = models.CharField(max_length=150)
    body = models.TextField()
    category = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title