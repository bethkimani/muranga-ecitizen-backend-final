import hashlib
import hmac
import logging
import os
import secrets
from datetime import timedelta
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OneTimeCode

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=getattr(settings, 'OTP_TTL_MINUTES', 15))
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5

# Frontend pages the email link opens
FRONTEND_PATHS = {
    'VERIFY': '/verify',
    'RESET': '/reset',
}

DEFAULT_FRONTEND_URL = 'https://muranga-ecitizen-frontend-final.vercel.app'


def _hash(user, purpose, code):
    raw = f'{user.pk}:{purpose}:{code}:{settings.SECRET_KEY}'
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_code(user, purpose, force=False):
    """Create a new 6-digit code. Returns the plain code, or None if the resend cooldown applies."""
    now = timezone.now()
    last = (
        OneTimeCode.objects.filter(user=user, purpose=purpose)
        .order_by('-created_at')
        .first()
    )
    if last and not force and now - last.created_at < RESEND_COOLDOWN:
        return None

    # Only one active code at a time
    OneTimeCode.objects.filter(user=user, purpose=purpose, used=False).update(used=True)

    code = f'{secrets.randbelow(1_000_000):06d}'
    OneTimeCode.objects.create(user=user, purpose=purpose, code_hash=_hash(user, purpose, code))
    return code


def check_code(user, purpose, code):
    """True if the code is valid. Marks it used on success; counts attempts on failure."""
    otp = (
        OneTimeCode.objects.filter(user=user, purpose=purpose, used=False)
        .order_by('-created_at')
        .first()
    )
    if not otp:
        return False
    if timezone.now() - otp.created_at > CODE_TTL or otp.attempts >= MAX_ATTEMPTS:
        otp.used = True
        otp.save(update_fields=['used'])
        return False

    if hmac.compare_digest(otp.code_hash, _hash(user, purpose, str(code).strip())):
        otp.used = True
        otp.save(update_fields=['used'])
        return True

    otp.attempts += 1
    otp.save(update_fields=['attempts'])
    return False


def _to_international(phone):
    p = phone.replace(' ', '').replace('-', '')
    if p.startswith('0'):
        return '+254' + p[1:]
    if p.startswith('254'):
        return '+' + p
    return p


def _frontend_url():
    """Frontend base URL without a trailing slash. Never raises if the setting is missing."""
    url = getattr(settings, 'FRONTEND_URL', '') or DEFAULT_FRONTEND_URL
    return url.rstrip('/')


def send_sms(phone, message):
    if not phone:
        return False

    # Accept both naming styles so settings.py and .env can use either.
    api_key = (
        getattr(settings, 'AFRICASTALKING_API_KEY', '')
        or getattr(settings, 'AT_API_KEY', '')
        or ''
    )
    username = (
        getattr(settings, 'AFRICASTALKING_USERNAME', '')
        or getattr(settings, 'AT_USERNAME', '')
        or 'sandbox'
    )

    # No real key yet: log instead of sending so registration still works
    if not api_key or api_key.startswith(('your_', 'PASTE')):
        logger.warning('[SMS not sent, no API key] to %s: %s', phone, message)
        return False

    base = 'api.sandbox.africastalking.com' if username == 'sandbox' else 'api.africastalking.com'
    try:
        r = requests.post(
            f'https://{base}/version1/messaging',
            headers={'apiKey': api_key, 'Accept': 'application/json'},
            data={'username': username, 'to': _to_international(phone), 'message': message},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception:
        logger.exception('SMS sending failed')
        return False


def send_email(to_email, subject, body):
    """Send via Brevo's HTTPS API if configured, else fall back to Django's email backend."""
    api_key = os.environ.get('BREVO_API_KEY', '')
    sender = os.environ.get('BREVO_SENDER_EMAIL', '')

    if api_key and sender:
        try:
            r = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'api-key': api_key,
                    'accept': 'application/json',
                    'content-type': 'application/json',
                },
                json={
                    'sender': {'name': "Murang'a e-Citizen", 'email': sender},
                    'to': [{'email': to_email}],
                    'subject': subject,
                    'textContent': body,
                },
                timeout=10,
            )
            if r.status_code >= 400:
                logger.error('Brevo rejected the email (%s): %s', r.status_code, r.text)
                return False
            return True
        except Exception:
            logger.exception('Brevo email sending failed')
            return False

    # No Brevo config: use whatever EMAIL_BACKEND is set (console backend prints to logs)
    try:
        send_mail(subject=subject, message=body, from_email=None, recipient_list=[to_email])
        return True
    except Exception:
        logger.exception('Email sending failed')
        return False


def deliver(user, purpose, code):
    """Send the code by email (if the user has one) and by SMS. Never raises."""
    if not code:
        return

    try:
        label = 'verify your account' if purpose == 'VERIFY' else 'reset your password'
        minutes = int(CODE_TTL.total_seconds() // 60)

        who = user.email or getattr(user, 'phone_number', '') or ''
        path = FRONTEND_PATHS.get(purpose, '/verify')
        link = f"{_frontend_url()}{path}?id={quote(who, safe='')}&code={code}"
        text = (
            f"Your Murang'a e-Citizen code to {label} is {code}. "
            f"It expires in {minutes} minutes. Do not share it with anyone."
        )
    except Exception:
        logger.exception('Could not build verification message')
        return

    if user.email:
        send_email(
            user.email,
            f"Murang'a e-Citizen: your code is {code}",
            f'{text}\n\nOr open this link:\n{link}',
        )

    send_sms(getattr(user, 'phone_number', ''), text)