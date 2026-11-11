from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from accounts.demo import DEMO_EMAIL, get_demo_user
from accounts.models import User
from vault.models import PasswordEntry
from vault.utils import encrypt_password


@override_settings(PUBLIC_DEMO_PASSWORD='Public-Sample-932!')
class PublicDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_public_demo', verbosity=0)
        cls.demo = get_demo_user()
        cls.owner = User.objects.create_user(
            email='private@example.test', password='Owner-Test-934!', email_verified=True,
        )
        PasswordEntry.objects.create(
            pk=1, user=cls.owner, website='private-vault.example',
            encrypted_password=encrypt_password('Owner-Only-Entry-369!'),
        )

    def sign_in(self, client=None, path='/accounts/login/'):
        client = client or self.client
        response = client.post(path, {'email': DEMO_EMAIL.upper(), 'password': 'Public-Sample-932!'})
        self.assertRedirects(response, '/vault/')
        return client

    def test_both_login_pages_display_credentials_and_accept_the_demo(self):
        for path in ['/accounts/login/', '/account/login/']:
            with self.subTest(path=path):
                client = Client()
                response = client.get(path)
                self.assertContains(response, DEMO_EMAIL)
                self.assertContains(response, 'Public-Sample-932!')
                self.assertIn('no-store', response['Cache-Control'])
                self.sign_in(client, path)
        self.assertFalse(self.demo.has_usable_password())
        self.assertFalse(self.demo.is_staff or self.demo.is_superuser)

    def test_demo_uses_synthetic_values_even_when_entry_ids_match(self):
        self.sign_in()
        response = self.client.get('/vault/')
        self.assertContains(response, 'mail.example')
        self.assertNotContains(response, 'private-vault.example')
        self.assertNotContains(response, 'Sample-Mail-47!')
        self.assertNotContains(response, 'data-delete-url=')
        self.assertNotContains(response, 'Add password')
        self.assertEqual(self.client.post('/vault/reveal/1/').json()['password'], 'Sample-Mail-47!')
        self.assertEqual(self.client.post('/vault/reveal/999/').status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post('/vault/reveal/1/').json()['password'], 'Owner-Only-Entry-369!')
        self.assertNotContains(self.client.get('/vault/'), 'mail.example')

    def test_demo_rejects_mutation_and_account_management(self):
        self.sign_in()
        for path in ['/vault/add/', '/vault/edit/1/', '/vault/delete/1/', '/vault/category/add/',
                     '/accounts/settings/', '/account/two_factor/setup/', '/admin/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
                self.assertEqual(self.client.post(path).status_code, 403)
        self.assertTrue(PasswordEntry.objects.filter(pk=1, user=self.owner).exists())
        self.assertFalse(PasswordEntry.objects.filter(user=self.demo).exists())
        self.assertRedirects(self.client.post('/accounts/logout/'), '/accounts/login/')

    def test_demo_login_and_sample_reveal_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/accounts/login/', {'email': DEMO_EMAIL, 'password': 'Public-Sample-932!'}).status_code, 403)
        client.get('/accounts/login/')
        response = client.post('/accounts/login/', {'email': DEMO_EMAIL, 'password': 'Public-Sample-932!',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.post('/vault/reveal/1/').status_code, 403)
        self.assertEqual(client.post('/vault/reveal/1/', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)

    def test_demo_password_reset_does_not_send_mail(self):
        self.assertEqual(self.client.post('/accounts/password_reset/', {'email': DEMO_EMAIL}).status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_disabling_demo_removes_card_and_invalidates_existing_session(self):
        self.sign_in()
        with override_settings(PUBLIC_DEMO_PASSWORD=''):
            self.assertRedirects(self.client.get('/vault/'), '/accounts/login/?next=/vault/')
            self.assertNotContains(self.client.get('/accounts/login/'), 'Public-Sample-932!')
            response = self.client.post('/accounts/login/', {'email': DEMO_EMAIL, 'password': 'Public-Sample-932!'})
            self.assertContains(response, 'Invalid credentials')
