
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'phone_number',
        'username',
        'email',
        'role',
        'department',
        'is_active',
    )

    list_filter = (
        'role',
        'department',
        'is_active',
        'is_staff',
    )

    search_fields = (
        'phone_number',
        'username',
        'email',
    )

    ordering = ('phone_number',)

    fieldsets = UserAdmin.fieldsets + (
        (
            'Portal details',
            {
                'fields': (
                    'role',
                    'phone_number',
                    'home_ward',
                    'sub_county',
                    'is_phone_verified',
                    'department',
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            'Portal details',
            {
                'fields': (
                    'role',
                    'phone_number',
                    'home_ward',
                    'sub_county',
                    'department',
                )
            },
        ),
    )
