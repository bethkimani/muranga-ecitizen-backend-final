from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


def check_email_free(value, instance=None):
    """Reject an email that another account already uses (case-insensitive)."""
    value = (value or '').strip()
    if not value:
        return value
    taken = User.objects.filter(email__iexact=value)
    if instance is not None:
        taken = taken.exclude(pk=instance.pk)
    if taken.exists():
        raise serializers.ValidationError('An account with this email address already exists.')
    return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'role', 'home_ward', 'sub_county', 'is_phone_verified',
        ]
        read_only_fields = ['id', 'role', 'is_phone_verified']

    def validate_email(self, value):
        return check_email_free(value, self.instance)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'phone_number', 'email', 'password',
            'first_name', 'last_name', 'home_ward', 'sub_county',
        ]

    def validate_email(self, value):
        return check_email_free(value)

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            phone_number=validated_data['phone_number'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            home_ward=validated_data.get('home_ward', ''),
            sub_county=validated_data.get('sub_county', ''),
        )
        return user