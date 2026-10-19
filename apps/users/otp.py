import base64
import hashlib
import hmac
import html
import logging
import os
import secrets
import threading
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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

# Email providers can be slow on the first call; allow longer and retry once.
EMAIL_TIMEOUT_SECONDS = 20
EMAIL_ATTEMPTS = 2

# Frontend pages the email link opens
FRONTEND_PATHS = {
    'VERIFY': '/verify',
    'RESET': '/reset',
}

DEFAULT_FRONTEND_URL = 'https://muranga-ecitizen-frontend-final.vercel.app'


def _hash(user, purpose, code):
    raw = f'{user.pk}:{purpose}:{code}:{settings.SECRET_KEY}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_code():
    """
    Return the 6-digit code.

    If OTP_FIXED_CODE is set in the environment (exactly 6 digits), that code is used
    for every user. This is for testing only. Remove the variable to go back to
    random codes.
    """
    fixed = os.environ.get('OTP_FIXED_CODE', '').strip()
    if len(fixed) == 6 and fixed.isdigit():
        logger.warning('OTP_FIXED_CODE is active: every account uses the same code. Testing only.')
        return fixed
    return f'{secrets.randbelow(1_000_000):06d}'


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
            timeout=EMAIL_TIMEOUT_SECONDS,
        )
        if tok.status_code >= 400:
            logger.error('Gmail token request failed (%s): %s', tok.status_code, tok.text)
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
            timeout=EMAIL_TIMEOUT_SECONDS,
        )
        if r.status_code >= 400:
            logger.error('Gmail API rejected the email (%s): %s', r.status_code, r.text)
            return False
        logger.info('Gmail API sent email to %s', to_email)
        return True
    except Exception:
        logger.exception('Gmail API sending failed')
        return False


def _send_brevo(to_email, subject, body, html_body=None):
    """Send via Brevo's HTTPS API. Returns None if not configured, True if accepted, False otherwise."""
    api_key = os.environ.get('BREVO_API_KEY', '')
    sender = os.environ.get('BREVO_SENDER_EMAIL', '')
    if not (api_key and sender):
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

    for attempt in range(1, EMAIL_ATTEMPTS + 1):
        try:
            r = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'api-key': api_key,
                    'accept': 'application/json',
                    'content-type': 'application/json',
                },
                json=payload,
                timeout=EMAIL_TIMEOUT_SECONDS,
            )
            if r.status_code >= 400:
                # A rejection will not fix itself on retry
                logger.error('Brevo rejected the email (%s): %s', r.status_code, r.text)
                return False
            logger.info('Brevo accepted email to %s (%s)', to_email, r.status_code)
            return True
        except (requests.Timeout, requests.ConnectionError):
            logger.warning('Brevo email attempt %s/%s timed out or lost connection', attempt, EMAIL_ATTEMPTS)
        except Exception:
            logger.exception('Brevo email sending failed')
            return False

    logger.error('Brevo email failed after %s attempts', EMAIL_ATTEMPTS)
    return False


def send_email(to_email, subject, body, html_body=None):
    """
    Try the Gmail API first (if configured), then Brevo (if configured),
    then Django's email backend (console backend prints to the logs).
    """
    result = send_gmail_api(to_email, subject, body, html_body)
    if result:
        return True

    result = _send_brevo(to_email, subject, body, html_body)
    if result:
        return True
    if result is False:
        # Brevo is configured but failed; do not fall through silently
        return False

    # Nothing configured: use whatever EMAIL_BACKEND is set
    try:
        send_mail(subject=subject, message=body, from_email=None, recipient_list=[to_email])
        return True
    except Exception:
        logger.exception('Email sending failed')
        return False


def _send_email_background(to_email, subject, body, html_body):
    """Run send_email in a background thread so the request does not wait for the provider."""

    def _run():
        try:
            send_email(to_email, subject, body, html_body)
        except Exception:
            logger.exception('Background email sending failed')

    threading.Thread(target=_run, daemon=True).start()


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
        _send_email_background(
            email,
            subject,
            f'{text}\n\nOr open this link:\n{link}',
            html_body,
        )

    send_sms(phone, text)