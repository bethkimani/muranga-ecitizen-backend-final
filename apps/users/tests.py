import logging
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from .login import LoginSerializer
from .otp import _generate_code, deliver, is_otp_required, send_email, send_gmail_api, send_sms
from .verification import ConfirmVerifyView, SendCodeView
from .views import RegisterView


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


class OtpRequiredSwitchTests(TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_otp_is_required_by_default(self):
        self.assertTrue(is_otp_required())

    @patch.dict(os.environ, {'OTP_REQUIRED': '0'})
    def test_otp_is_disabled_only_by_zero(self):
        self.assertFalse(is_otp_required())

    @patch.dict(os.environ, {'OTP_REQUIRED': '1'})
    def test_otp_can_be_enabled(self):
        self.assertTrue(is_otp_required())

    @patch('apps.users.views.deliver')
    @patch('apps.users.views.issue_code')
    @patch('apps.users.views.is_otp_required', return_value=False)
    def test_register_marks_user_verified_without_issuing_or_sending_code(
        self, otp_required_mock, issue_code_mock, deliver_mock
    ):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username='otp-disabled',
            phone_number='0712345678',
            email='otp-disabled@example.com',
            password='safe-test-password',
        )
        serializer = SimpleNamespace(save=lambda: user)

        RegisterView().perform_create(serializer)

        user.refresh_from_db()
        self.assertTrue(user.is_phone_verified)
        issue_code_mock.assert_not_called()
        deliver_mock.assert_not_called()

    @patch.dict(os.environ, {'OTP_REQUIRED': '0'})
    def test_login_allows_existing_unverified_user_when_otp_disabled(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username='unverified',
            phone_number='0712345679',
            email='unverified@example.com',
            password='safe-test-password',
            is_phone_verified=False,
        )
        serializer = LoginSerializer(
            data={
                'identifier': 'unverified@example.com',
                'password': 'safe-test-password',
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn('access', serializer.validated_data)
        self.assertIn('refresh', serializer.validated_data)

    @patch.dict(os.environ, {'OTP_REQUIRED': '1'})
    def test_login_still_rejects_unverified_user_when_otp_enabled(self):
        from django.contrib.auth import get_user_model
        from rest_framework.exceptions import PermissionDenied

        get_user_model().objects.create_user(
            username='unverified-required',
            phone_number='0712345680',
            email='unverified-required@example.com',
            password='safe-test-password',
            is_phone_verified=False,
        )
        serializer = LoginSerializer()

        with self.assertRaises(PermissionDenied):
            serializer.validate(
                {
                    'identifier': 'unverified-required@example.com',
                    'password': 'safe-test-password',
                }
            )

    @patch.dict(os.environ, {'OTP_REQUIRED': '0'})
    @patch('apps.users.verification.find_user')
    @patch('apps.users.verification.issue_code')
    @patch('apps.users.verification.deliver')
    def test_verify_endpoints_return_ok_without_lookup_or_delivery(
        self, deliver_mock, issue_code_mock, find_user_mock
    ):
        factory = APIRequestFactory()
        send_response = SendCodeView.as_view(purpose='VERIFY')(
            factory.post(
                '/api/auth/verify/send/',
                {'identifier': 'resident@example.com'},
                format='json',
            )
        )
        confirm_response = ConfirmVerifyView.as_view()(
            factory.post(
                '/api/auth/verify/confirm/',
                {'identifier': 'resident@example.com', 'code': '123456'},
                format='json',
            )
        )

        self.assertEqual(send_response.status_code, 200)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(send_response.data, {'detail': 'Account verification is disabled.'})
        self.assertEqual(confirm_response.data, {'detail': 'Account verification is disabled.'})
        find_user_mock.assert_not_called()
        issue_code_mock.assert_not_called()
        deliver_mock.assert_not_called()

    @patch.dict(os.environ, {'OTP_REQUIRED': '0'})
    @patch('apps.users.verification.find_user')
    @patch('apps.users.verification.issue_code', return_value='654321')
    @patch('apps.users.verification.deliver')
    def test_disabling_account_verification_does_not_disable_password_reset_codes(
        self, deliver_mock, issue_code_mock, find_user_mock
    ):
        find_user_mock.return_value = SimpleNamespace(is_active=True, is_phone_verified=False)
        request = APIRequestFactory().post(
            '/api/auth/password/forgot/',
            {'identifier': 'resident@example.com'},
            format='json',
        )

        response = SendCodeView.as_view(purpose='RESET')(request)

        self.assertEqual(response.status_code, 200)
        issue_code_mock.assert_called_once()
        deliver_mock.assert_called_once()


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
