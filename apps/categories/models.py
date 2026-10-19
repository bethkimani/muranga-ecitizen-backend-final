from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    head_officer_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=150)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='categories')
    description = models.TextField()
    response_target_days = models.IntegerField(default=3)
    icon_name = models.CharField(max_length=50, default='HelpCircleIcon')

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.name} ({self.department.name})"