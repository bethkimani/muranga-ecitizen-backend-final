from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.login import normalize_phone
from apps.users.otp import deliver, issue_code
from apps.users.serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        code = issue_code(user, 'VERIFY', force=True)
        deliver(user, 'VERIFY', code)


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