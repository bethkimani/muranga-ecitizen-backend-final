import base64
import hashlib
import hmac
import html
import logging
import math
import os
import secrets
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import OneTimeCode

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=getattr(settings, 'OTP_TTL_MINUTES', 15))
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5

# Keep synchronous provider calls short enough for Render's request worker.
PROVIDER_TIMEOUT_SECONDS = 2

# Frontend pages the email link opens
FRONTEND_PATHS = {
    'VERIFY': '/verify',
    'RESET': '/reset',
}

DEFAULT_FRONTEND_URL = 'https://muranga-ecitizen-frontend-final.vercel.app'


def is_otp_required():
    """
    Return whether account verification OTP is enabled.

    DISABLED by default for now. To turn it on later, set the environment
    variable OTP_REQUIRED=1 on Render.
    """
    return os.environ.get('OTP_REQUIRED', '0').strip() == '1'


def auto_verify(user):
    """Mark the account as verified without a code (used while OTP is off)."""
    if not getattr(user, 'is_phone_verified', False):
        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])


def _hash(user, purpose, code):
    raw = f'{user.pk}:{purpose}:{code}:{settings.SECRET_KEY}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_code():
    """
    Return a random 6-digit code unless fixed-code testing is explicitly enabled.
    """
    fixed = os.environ.get('OTP_FIXED_CODE', '').strip()
    if os.environ.get('ALLOW_FIXED_OTP') == '1':
        if len(fixed) == 6 and fixed.isdigit():
            logger.warning('Fixed OTP testing is enabled; using a non-random OTP')
            return fixed
        logger.error('ALLOW_FIXED_OTP is enabled but OTP_FIXED_CODE is not six digits')
    elif fixed:
        logger.error('Ignoring OTP_FIXED_CODE because ALLOW_FIXED_OTP is not set to 1')
    return f'{secrets.randbelow(1_000_000):06d}'


def resend_cooldown_seconds(user, purpose):
    """Return the remaining resend cooldown, rounded up to a whole second."""
    last = (
        OneTimeCode.objects.filter(user=user, purpose=purpose)
        .order_by('-created_at')
        .first()
    )
    if not last:
        return 0
    remaining = RESEND_COOLDOWN - (timezone.now() - last.created_at)
    return max(0, math.ceil(remaining.total_seconds()))


def issue_code(user, purpose, force=False):
    """Create a new 6-digit code. Returns the plain code, or None if the resend cooldown applies."""
    with transaction.atomic():
        type(user).objects.select_for_update().get(pk=user.pk)
        if not force and resend_cooldown_seconds(user, purpose):
            return None

        # Only one active code at a time
        OneTimeCode.objects.filter(user=user, purpose=purpose, used=False).update(used=True)

        code = _generate_code()
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


def _provider_error_reason(response):
    """Extract a provider's public error reason without logging request credentials."""
    try:
        payload = response.json()
    except ValueError:
        return 'non-JSON error response'

    if not isinstance(payload, dict):
        return 'provider returned an unexpected error response'

    error = payload.get('error')
    if isinstance(error, dict):
        error_details = error.get('errors', [])
        if not isinstance(error_details, list):
            error_details = []
        reasons = [
            item.get('reason')
            for item in error_details
            if isinstance(item, dict) and item.get('reason')
        ]
        message = error.get('message')
        return '; '.join(str(part) for part in (reasons[0] if reasons else '', message) if part)
    if isinstance(error, str):
        return '; '.join(str(part) for part in (error, payload.get('error_description')) if part)

    return str(payload.get('message') or payload.get('code') or 'unspecified provider error')


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
        logger.warning('[SMS not sent, no API key]')
        return False

    base = 'api.sandbox.africastalking.com' if username == 'sandbox' else 'api.africastalking.com'
    try:
        r = requests.post(
            f'https://{base}/version1/messaging',
            headers={'apiKey': api_key, 'Accept': 'application/json'},
            data={'username': username, 'to': _to_international(phone), 'message': message},
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        return True
    except Exception:
        logger.exception('SMS sending failed')
        return False


def send_gmail_api(to_email, subject, body, html_body=None):
    """
    Send through the Gmail API (HTTPS, works on Render's free plan).

    Needs these environment variables:
      GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_SENDER

    Returns None if not configured, True if sent, False if it failed.
    """
    client_id = os.environ.get('GMAIL_CLIENT_ID', '')
    client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '')
    refresh_token = os.environ.get('GMAIL_REFRESH_TOKEN', '')
    sender = os.environ.get('GMAIL_SENDER', '')
    if not (client_id and client_secret and refresh_token and sender):
        logger.info('provider=gmail recipient=%s result=not_configured', to_email)
        return None

    try:
        tok = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )
        if tok.status_code >= 400:
            logger.error(
                'provider=gmail recipient=%s result=failed stage=token status=%s reason=%s',
                to_email,
                tok.status_code,
                _provider_error_reason(tok),
            )
            return False
        access_token = tok.json()['access_token']

        msg = MIMEMultipart('alternative')
        msg['To'] = to_email
        msg['From'] = f"Murang'a e-Citizen <{sender}>"
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        r = requests.post(
            'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
            headers={'Authorization': f'Bearer {access_token}'},
            json={'raw': raw},
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )
        if r.status_code >= 400:
            logger.error(
                'provider=gmail recipient=%s result=failed stage=send status=%s reason=%s',
                to_email,
                r.status_code,
                _provider_error_reason(r),
            )
            return False
        logger.info('provider=gmail recipient=%s result=accepted status=%s', to_email, r.status_code)
        return True
    except requests.RequestException as exc:
        logger.error(
            'provider=gmail recipient=%s result=failed reason=%s',
            to_email,
            type(exc).__name__,
        )
        return False
    except (KeyError, ValueError) as exc:
        logger.error(
            'provider=gmail recipient=%s result=failed reason=%s',
            to_email,
            type(exc).__name__,
        )
        return False


def _send_brevo(to_email, subject, body, html_body=None):
    """Send via Brevo's HTTPS API once. Returns None if not configured."""
    api_key = os.environ.get('BREVO_API_KEY', '')
    sender = os.environ.get('BREVO_SENDER_EMAIL', '')
    if not (api_key and sender):
        logger.info('provider=brevo recipient=%s result=not_configured', to_email)
        return None

    payload = {
        'sender': {'name': "Murang'a e-Citizen", 'email': sender},
        'replyTo': {'name': "Murang'a e-Citizen", 'email': sender},
        'to': [{'email': to_email}],
        'subject': subject,
        'textContent': body,
    }
    if html_body:
        payload['htmlContent'] = html_body

    try:
        r = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'api-key': api_key,
                'accept': 'application/json',
                'content-type': 'application/json',
            },
            json=payload,
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.error(
            'provider=brevo recipient=%s result=failed reason=%s',
            to_email,
            type(exc).__name__,
        )
        return False

    if r.status_code >= 400:
        logger.error(
            'provider=brevo recipient=%s result=failed status=%s reason=%s',
            to_email,
            r.status_code,
            _provider_error_reason(r),
        )
        return False
    logger.info('provider=brevo recipient=%s result=accepted status=%s', to_email, r.status_code)
    return True


def send_email(to_email, subject, body, html_body=None):
    """
    Try configured HTTPS providers. The local console backend is only used in DEBUG.
    """
    result = send_gmail_api(to_email, subject, body, html_body)
    if result:
        return True

    brevo_result = _send_brevo(to_email, subject, body, html_body)
    if brevo_result:
        return True

    if result is False or brevo_result is False:
        # A configured API provider failed; don't hide its failure with another backend.
        return False

    if not (settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'):
        logger.error(
            'provider=none recipient=%s result=failed reason=no HTTPS email provider accepted the message',
            to_email,
        )
        return False

    try:
        sent = send_mail(subject=subject, message=body, from_email=None, recipient_list=[to_email])
        logger.info('provider=django-console recipient=%s result=%s', to_email, 'accepted' if sent else 'failed')
        return sent == 1
    except Exception as exc:
        logger.error(
            'provider=django-console recipient=%s result=failed reason=%s',
            to_email,
            type(exc).__name__,
        )
        return False


def _build_html(label, code, minutes, link):
    safe_label = html.escape(label)
    safe_code = html.escape(code)
    safe_link = html.escape(link, quote=True)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;'
        'padding:24px;color:#1f2937">'
        "<h2 style=\"margin:0 0 12px;color:#047857\">Murang'a e-Citizen</h2>"
        f'<p>Use this code to {safe_label}:</p>'
        f'<p style="font-size:32px;letter-spacing:6px;font-weight:bold;margin:16px 0">{safe_code}</p>'
        f'<p>It expires in {minutes} minutes. Do not share it with anyone.</p>'
        f'<p><a href="{safe_link}" style="display:inline-block;background:#047857;color:#ffffff;'
        'padding:10px 18px;border-radius:6px;text-decoration:none">Open the verification page</a></p>'
        '<p style="font-size:12px;color:#6b7280;margin-top:24px">If you did not request this, '
        'you can ignore this email.</p>'
        '</div>'
    )


def deliver(user, purpose, code):
    """Send the code by email (if the user has one) and by SMS. Never raises."""
    # Verification is switched off: verify the account straight away and send nothing.
    # Password-reset codes are still delivered normally.
    if purpose == 'VERIFY' and not is_otp_required():
        try:
            auto_verify(user)
        except Exception:
            logger.exception('Could not auto-verify user %s', getattr(user, 'pk', None))
        return

    if not code:
        return

    try:
        label = 'verify your account' if purpose == 'VERIFY' else 'reset your password'
        subject = (
            "Verify your Murang'a e-Citizen account"
            if purpose == 'VERIFY'
            else "Reset your Murang'a e-Citizen password"
        )
        minutes = int(CODE_TTL.total_seconds() // 60)

        who = user.email or getattr(user, 'phone_number', '') or ''
        path = FRONTEND_PATHS.get(purpose, '/verify')
        link = f"{_frontend_url()}{path}?id={quote(who, safe='')}&code={code}"
        text = (
            f"Your Murang'a e-Citizen code to {label} is {code}. "
            f"It expires in {minutes} minutes. Do not share it with anyone."
        )
        email = user.email
        phone = getattr(user, 'phone_number', '')
        html_body = _build_html(label, code, minutes, link)
    except Exception:
        logger.exception('Could not build verification message')
        return

    if email:
        send_email(
            email,
            subject,
            f'{text}\n\nOr open this link:\n{link}',
            html_body,
        )

    send_sms(phone, text)