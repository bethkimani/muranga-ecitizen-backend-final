import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.login import normalize_phone
from apps.users.otp import deliver, issue_code
from apps.users.serializers import RegisterSerializer, UserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        # Create the user and their code together: both succeed or neither does.
        with transaction.atomic():
            user = serializer.save()
            code = issue_code(user, 'VERIFY', force=True)

        # Sending happens after the commit. A failed email/SMS must never
        # turn a successful registration into a 500.
        try:
            deliver(user, 'VERIFY', code)
        except Exception:
            logger.exception('Could not deliver verification code for user %s', user.pk)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        data = {k: v for k, v in request.data.items() if k in ('first_name', 'last_name', 'email')}
        phone = request.data.get('phone_number') or request.data.get('phone')
        if phone:
            data['phone_number'] = normalize_phone(phone)
        serializer = UserSerializer(request.user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)