"""Exercise account emails through the real Mailjet adapter without network I/O."""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from requests import Response

from accounts.models import User


@override_settings(
    EMAIL_BACKEND='anymail.backends.mailjet.EmailBackend',
    DEFAULT_FROM_EMAIL='sender@example.test',
    ANYMAIL={
        'MAILJET_API_KEY': 'synthetic-public-key',
        'MAILJET_SECRET_KEY': 'synthetic-private-key',
        'REQUESTS_TIMEOUT': 15,
        'SEND_DEFAULTS': {'track_clicks': False, 'track_opens': False},
    },
)
class MailjetDeliveryTests(TestCase):
    password = 'Mailjet-Validation-Password-293!'

    def registration(self):
        return self.client.post(reverse('accounts:register'), {
            'email': 'new@example.test', 'first_name': 'New', 'last_name': 'User',
            'password1': self.password, 'password2': self.password,
        })

    def api_response(self, code=200):
        response = Response()
        response.status_code = code
        response.headers['Content-Type'] = 'application/json'
        response.reason = 'OK' if code == 200 else 'Bad Request'
        body = {'Messages': [{'Status': 'success', 'To': [
            {'Email': 'new@example.test', 'MessageID': 12345},
        ]}]} if code == 200 else {'ErrorCode': 'blocked', 'ErrorMessage': 'Account pending activation'}
        response._content = json.dumps(body).encode()
        return response

    @patch('requests.sessions.Session.request')
    def test_verification_uses_mailjet_with_tracking_disabled(self, request):
        request.return_value = self.api_response()
        response = self.registration()
        self.assertContains(response, 'new@example.test')
        self.assertTrue(User.objects.filter(email='new@example.test', email_verified=False).exists())
        args, kwargs = request.call_args
        self.assertEqual(kwargs['url'], 'https://api.mailjet.com/v3.1/send')
        self.assertEqual(kwargs['auth'], ('synthetic-public-key', 'synthetic-private-key'))
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['Globals']['From']['Email'], 'sender@example.test')
        self.assertIn('/accounts/verify/', payload['Globals']['HTMLPart'])
        self.assertEqual(payload['Globals']['TrackClicks'], 'disabled')
        self.assertEqual(payload['Globals']['TrackOpens'], 'disabled')

    @patch('requests.sessions.Session.request')
    def test_provider_rejection_rolls_back_registration(self, request):
        request.return_value = self.api_response(400)
        response = self.registration()
        self.assertContains(response, 'Email could not be sent')
        self.assertNotContains(response, 'pending activation')
        self.assertFalse(User.objects.filter(email='new@example.test').exists())

    @patch('requests.sessions.Session.request')
    def test_reset_uses_mailjet(self, request):
        User.objects.create_user(email='new@example.test', password=self.password, email_verified=True)
        request.return_value = self.api_response()
        response = self.client.post(reverse('accounts:password_reset'), {'email': 'new@example.test'})
        self.assertEqual(response.status_code, 302)
        payload = json.loads(request.call_args.kwargs['data'])
        self.assertIn('/accounts/reset/', payload['Globals']['TextPart'])

    @patch('requests.sessions.Session.request')
    def test_resend_handles_provider_rejection(self, request):
        User.objects.create_user(email='new@example.test', password=self.password, email_verified=False)
        request.return_value = self.api_response(400)
        response = self.client.post(reverse('accounts:resend_verification'), {'email': 'new@example.test'})
        self.assertContains(response, 'Email service is unavailable')
