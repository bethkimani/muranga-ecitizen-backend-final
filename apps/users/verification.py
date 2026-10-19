import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .login import normalize_phone
from .otp import check_code, deliver, is_otp_required, issue_code, resend_cooldown_seconds

User = get_user_model()
logger = logging.getLogger(__name__)
GENERIC = {'detail': 'If the account exists, the code request has been processed.'}


def get_identifier(request):
    """Accepts `identifier` (preferred) or `id`, so older frontend code still works."""
    return request.data.get('identifier') or request.data.get('id') or ''


def find_user(identifier):
    identifier = (identifier or '').strip()
    if not identifier:
        return None
    if '@' in identifier:
        matches = list(User.objects.filter(email__iexact=identifier)[:2])
        return matches[0] if len(matches) == 1 else None
    return User.objects.filter(phone_number=normalize_phone(identifier)).first()


class SendCodeView(APIView):
    """Used for both verify-send and forgot-password. Set purpose in urls.py."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    purpose = None

    def post(self, request):
        if self.purpose == 'VERIFY' and not is_otp_required():
            return Response({'detail': 'Account verification is disabled.'})

        user = find_user(get_identifier(request))
        # Same response whether or not the account exists, so nobody can probe for accounts
        if user and user.is_active:
            if not (self.purpose == 'VERIFY' and user.is_phone_verified):
                code = issue_code(user, self.purpose)  # None if resent within 60 seconds
                if code is None:
                    retry_after = max(1, resend_cooldown_seconds(user, self.purpose))
                    response = Response(
                        {
                            'detail': (
                                f'A code was generated recently. If you have not received it, '
                                f'you can request another in {retry_after} seconds.'
                            ),
                            'retry_after': retry_after,
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                    response['Retry-After'] = str(retry_after)
                    return response
                deliver(user, self.purpose, code)
        return Response(GENERIC)


class ConfirmVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        if not is_otp_required():
            return Response({'detail': 'Account verification is disabled.'})

        identifier = get_identifier(request)
        code = str(request.data.get('code', '')).strip()
        user = find_user(identifier)

        if not user:
            logger.warning('verify: no single account found for %r', identifier)
            return Response({'detail': 'Invalid or expired code.'}, status=status.HTTP_400_BAD_REQUEST)

        # Already verified (for example the email link ran twice): treat as success
        if user.is_phone_verified:
            return Response({'detail': 'Account already verified. You can now log in.'})

        if not check_code(user, 'VERIFY', code):
            logger.warning('verify: wrong, expired or used code for user %s', user.pk)
            return Response({'detail': 'Invalid or expired code.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])
        return Response({'detail': 'Account verified. You can now log in.'})


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        user = find_user(get_identifier(request))
        code = str(request.data.get('code', '')).strip()
        new_password = request.data.get('new_password', '')
        if not user or not check_code(user, 'RESET', code):
            return Response({'detail': 'Invalid or expired code.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.is_phone_verified = True  # they proved they control the phone or email
        user.save()
        return Response({'detail': 'Password changed. You can now log in.'})


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.check_password(request.data.get('old_password', '')):
            return Response({'old_password': ['Current password is wrong.']}, status=status.HTTP_400_BAD_REQUEST)
        new_password = request.data.get('new_password', '')
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password updated.'})