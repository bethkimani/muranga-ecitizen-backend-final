import hashlib
import hmac
import logging
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

# Next.js pages the email link opens
FRONTEND_PATHS = {
    'VERIFY': '/verify',
    'RESET': '/reset',
}


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


def send_sms(phone, message):
    api_key = getattr(settings, 'AT_API_KEY', '') or ''
    username = getattr(settings, 'AT_USERNAME', 'sandbox') or 'sandbox'

    # No real key yet: print to the terminal so you can keep testing
    if not api_key or api_key.startswith(('your_', 'PASTE')):
        print(f'[SMS to {phone}] {message}')
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


def deliver(user, purpose, code):
    """Send the code by email (if the user has one) and by SMS."""
    if not code:
        return
    label = 'verify your account' if purpose == 'VERIFY' else 'reset your password'
    minutes = int(CODE_TTL.total_seconds() // 60)

    who = user.email or user.phone_number
    link = (
        f"{settings.FRONTEND_URL}{FRONTEND_PATHS[purpose]}"
        f"?id={quote(who, safe='')}&code={code}"
    )
    text = (
        f"Your Murang'a e-Citizen code to {label} is {code}. "
        f"It expires in {minutes} minutes. Do not share it with anyone."
    )

    if user.email:
        try:
            send_mail(
                subject=f"Murang'a e-Citizen: your code is {code}",
                message=f'{text}\n\nOr open this link:\n{link}',
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[user.email],
            )
        except Exception:
            logger.exception('Email sending failed')

    send_sms(user.phone_number, text)