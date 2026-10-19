import logging
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from .otp import _generate_code, deliver, send_email, send_gmail_api, send_sms
from .verification import SendCodeView


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

        gmail_mock.assert_called_once()
        brevo_mock.assert_called_once()
        send_mail_mock.assert_not_called()


class OtpConfigurationTests(TestCase):
    @override_settings(DEBUG=True)
    @patch.dict(os.environ, {'OTP_FIXED_CODE': '123456', 'ALLOW_FIXED_OTP': '0'})
    @patch('apps.users.otp.secrets.randbelow', return_value=7)
    def test_fixed_otp_is_ignored_without_explicit_flag_even_in_debug(self, randbelow_mock):
        self.assertEqual(_generate_code(), '000007')
        randbelow_mock.assert_called_once_with(1_000_000)

    @override_settings(DEBUG=False)
    @patch.dict(os.environ, {'OTP_FIXED_CODE': '123456', 'ALLOW_FIXED_OTP': '1'})
    def test_fixed_otp_requires_flag_but_not_debug_mode(self):
        self.assertEqual(_generate_code(), '123456')

    @patch('apps.users.otp.settings.AT_API_KEY', '')
    @patch('apps.users.otp.settings.AFRICASTALKING_API_KEY', '')
    def test_missing_sms_credentials_do_not_log_the_message(self):
        with self.assertLogs('apps.users.otp', level=logging.WARNING) as logs:
            self.assertFalse(send_sms('0712345678', 'Your code is 123456'))

        self.assertNotIn('123456', '\n'.join(logs.output))


class VerifySendCooldownTests(TestCase):
    @patch('apps.users.verification.deliver')
    @patch('apps.users.verification.resend_cooldown_seconds', return_value=17)
    @patch('apps.users.verification.issue_code', return_value=None)
    @patch(
        'apps.users.verification.find_user',
        return_value=SimpleNamespace(is_active=True, is_phone_verified=False),
    )
    def test_send_code_returns_429_during_cooldown(
        self, find_user_mock, issue_code_mock, cooldown_mock, deliver_mock
    ):
        request = APIRequestFactory().post(
            '/api/auth/verify/send/',
            {'identifier': 'resident@example.com'},
            format='json',
        )
        response = SendCodeView.as_view(purpose='VERIFY')(request)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '17')
        self.assertEqual(response.data['retry_after'], 17)
        self.assertIn('17 seconds', response.data['detail'])
        find_user_mock.assert_called_once_with('resident@example.com')
        issue_code_mock.assert_called_once()
        cooldown_mock.assert_called_once()
        deliver_mock.assert_not_called()


class GmailApiTests(TestCase):
    @patch.dict(
        os.environ,
        {
            'GMAIL_CLIENT_ID': 'client-id',
            'GMAIL_CLIENT_SECRET': 'client-secret',
            'GMAIL_REFRESH_TOKEN': 'refresh-secret',
            'GMAIL_SENDER': 'sender@gmail.com',
        },
    )
    @patch('apps.users.otp.requests.post')
    def test_gmail_api_uses_refreshed_bearer_token(self, post_mock):
        token_response = SimpleNamespace(
            status_code=200,
            json=lambda: {'access_token': 'temporary-access-token'},
        )
        send_response = SimpleNamespace(status_code=200)
        post_mock.side_effect = [token_response, send_response]

        self.assertTrue(
            send_gmail_api('recipient@gmail.com', 'OTP', 'A code was requested.')
        )

        self.assertEqual(
            post_mock.call_args_list[1].kwargs['headers']['Authorization'],
            'Bearer temporary-access-token',
        )

    @patch.dict(
        os.environ,
        {
            'GMAIL_CLIENT_ID': 'client-id',
            'GMAIL_CLIENT_SECRET': 'client-secret',
            'GMAIL_REFRESH_TOKEN': 'refresh-secret',
            'GMAIL_SENDER': 'sender@gmail.com',
        },
    )
    @patch('apps.users.otp.requests.post')
    def test_gmail_oauth_error_logs_google_reason_not_credentials(self, post_mock):
        token_response = SimpleNamespace(
            status_code=400,
            json=lambda: {
                'error': 'invalid_grant',
                'error_description': 'Token has been expired or revoked.',
            },
        )
        post_mock.return_value = token_response

        with self.assertLogs('apps.users.otp', level=logging.ERROR) as logs:
            self.assertFalse(
                send_gmail_api('recipient@gmail.com', 'OTP', 'A code was requested.')
            )

        output = '\n'.join(logs.output)
        self.assertIn('invalid_grant', output)
        self.assertIn('Token has been expired or revoked.', output)
        self.assertNotIn('refresh-secret', output)
