from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class UserRole(models.TextChoices):
    CITIZEN = 'CITIZEN', 'Citizen'
    STAFF = 'STAFF', 'Field / Desk Officer'
    DEPT_HEAD = 'DEPT_HEAD', 'Department Head'
    ADMIN = 'ADMIN', 'County Admin'


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CITIZEN,
    )

    phone_number = models.CharField(
        max_length=15,
        unique=True,
    )

    home_ward = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    sub_county = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    # Reused to mean "account verified" (email or phone code confirmed).
    is_phone_verified = models.BooleanField(default=False)

    department = models.ForeignKey(
        'categories.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
    )

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['username', 'email']

    class Meta(AbstractUser.Meta):
        # One account per email address, ignoring capitals. Blank emails are allowed to repeat.
        constraints = [
            models.UniqueConstraint(
                Lower('email'),
                condition=~models.Q(email=''),
                name='unique_user_email_ci',
            )
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


class OneTimeCode(models.Model):
    class Purpose(models.TextChoices):
        VERIFY = 'VERIFY', 'Verify account'
        RESET = 'RESET', 'Reset password'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='one_time_codes',
    )
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user_id} {self.purpose} ({'used' if self.used else 'active'})"