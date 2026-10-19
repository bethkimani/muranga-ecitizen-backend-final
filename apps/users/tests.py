import logging
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from .otp import _generate_code, deliver, send_email, send_sms


class EmailDeliveryTests(TestCase):
    @patch('apps.users.otp.send_sms')
    @patch('apps.users.otp.send_email')
    def test_deliver_sends_email_before_returning(self, send_email_mock, send_sms_mock):
        user = SimpleNamespace(email='resident@example.com', phone_number='')

        deliver(user, 'VERIFY', '123456')

        send_email_mock.assert_called_once()
        send_sms_mock.assert_called_once()

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    @patch('apps.users.otp.send_mail')
    @patch('apps.users.otp._send_brevo', return_value=None)
    @patch('apps.users.otp.send_gmail_api', return_value=None)
    def test_production_console_backend_does_not_report_email_as_sent(
        self, gmail_mock, brevo_mock, send_mail_mock
    ):
        self.assertFalse(send_email('resident@example.com', 'Subject', 'Body'))

        send_mail_mock.assert_not_called()


class OtpConfigurationTests(TestCase):
    @override_settings(DEBUG=False)
    @patch.dict(os.environ, {'OTP_FIXED_CODE': '123456'})
    @patch('apps.users.otp.secrets.randbelow', return_value=7)
    def test_fixed_otp_is_ignored_when_debug_is_disabled(self, randbelow_mock):
        self.assertEqual(_generate_code(), '000007')
        randbelow_mock.assert_called_once_with(1_000_000)

    @override_settings(DEBUG=True)
    @patch.dict(os.environ, {'OTP_FIXED_CODE': '123456'})
    def test_fixed_otp_is_allowed_in_debug_mode(self):
        self.assertEqual(_generate_code(), '123456')

    @patch('apps.users.otp.settings.AT_API_KEY', '')
    @patch('apps.users.otp.settings.AFRICASTALKING_API_KEY', '')
    def test_missing_sms_credentials_do_not_log_the_message(self):
        with self.assertLogs('apps.users.otp', level=logging.WARNING) as logs:
            self.assertFalse(send_sms('0712345678', 'Your code is 123456'))

        self.assertNotIn('123456', '\n'.join(logs.output))
