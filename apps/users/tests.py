from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from .otp import deliver, send_email


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
