"""Regression tests for account security, 2FA, and vault behavior."""
import contextlib
from base64 import b32decode
import io
from pathlib import Path
import re
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth.hashers import make_password
from accounts.tokens import email_verification_token as default_token_generator
from django.core import mail
from django.conf import settings
from django.core.cache import cache
from django.template import engines
from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import RecoveryCode, User, get_fernet
from vault.models import Category, PasswordEntry
from vault.utils import decrypt_password, encrypt_password, generate_password


class ValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Validation-Strong-Password-972!'
        cls.user = User.objects.create_user(
            email='alice@example.test', password=cls.password,
            first_name='Alice', last_name='Tester', email_verified=True,
        )
        cls.other = User.objects.create_user(
            email='bob@example.test', password=cls.password,
            first_name='Bob', last_name='Tester', email_verified=True,
        )
        cls.category = Category.objects.create(user=cls.user, name='Personal')
        cls.other_category = Category.objects.create(user=cls.other, name='Private')

    def signed_in(self, user=None, csrf=False):
        client = Client(enforce_csrf_checks=csrf)
        client.force_login(user or self.user)
        return client

    def setUp(self):
        cache.clear()

    def entry(self, user=None, password='Saved-Password-123!'):
        encrypted = encrypt_password(password)
        return PasswordEntry.objects.create(
            user=user or self.user, website='example.test', username='alice',
            encrypted_password=encrypted,
        )

    def test_public_pages_render(self):
        for name in ['login', 'register', 'password_reset', 'password_reset_done',
                     'password_reset_complete', 'recovery_login']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse('accounts:' + name)).status_code, 200)

    def test_project_templates_compile(self):
        for path in sorted((Path(settings.BASE_DIR) / 'templates').rglob('*.html')):
            with self.subTest(template=str(path.relative_to(settings.BASE_DIR))):
                engines['django'].from_string(path.read_text())

    def test_vault_requires_authentication(self):
        for name in ['dashboard', 'add_password', 'add_category', 'generate_password', 'check_strength']:
            with self.subTest(page=name):
                response = self.client.get(reverse('vault:' + name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/accounts/login/', response.url)

    def test_registration_sends_verification(self):
        response = self.client.post(reverse('accounts:register'), {
            'email': 'new@example.test', 'first_name': 'New', 'last_name': 'Tester',
            'password1': self.password, 'password2': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(User.objects.get(email='new@example.test').email_verified)
        self.assertIn('/accounts/verify/', mail.outbox[0].body)

    def test_email_verification(self):
        self.user.email_verified = False
        self.user.save()
        url = reverse('accounts:verify_email', args=[
            urlsafe_base64_encode(force_bytes(self.user.pk)),
            default_token_generator.make_token(self.user),
        ])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_verified_user_login(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': self.user.email, 'password': self.password,
        })
        self.assertRedirects(response, reverse('vault:dashboard'))

    def test_unverified_user_blocked_on_custom_login(self):
        self.user.email_verified = False
        self.user.save()
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_unverified_user_blocked_on_alternate_login(self):
        self.user.email_verified = False
        self.user.save()
        self.client.post(reverse('two_factor:login'), {
            'email': self.user.email, 'password': self.password,
        })
        response = self.client.get(reverse('vault:dashboard'))
        self.assertFalse(response.wsgi_request.user.is_authenticated,
                         'An unverified account can access the vault through the package login.')

    def test_password_reset_email(self):
        response = self.client.post(reverse('accounts:password_reset'), {'email': self.user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)

    def test_vault_password_crud_and_encryption(self):
        client = self.signed_in()
        response = client.post(reverse('vault:add_password'), {
            'website': 'example.test', 'username': 'alice',
            'password': 'Saved-Password-123!', 'category': self.category.pk,
        })
        self.assertEqual(response.status_code, 302)
        entry = PasswordEntry.objects.get(user=self.user)
        self.assertNotIn(b'Saved-Password-123!', bytes(entry.encrypted_password))
        self.assertEqual(decrypt_password(entry.encrypted_password), 'Saved-Password-123!')
        self.assertContains(client.get(reverse('vault:dashboard')), 'example.test')
        self.assertEqual(client.get(reverse('vault:edit_password', args=[entry.pk])).status_code, 200)
        response = client.post(reverse('vault:edit_password', args=[entry.pk]), {
            'website': 'updated.test', 'username': 'alice', 'password': 'Updated-Password-456!',
        })
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(decrypt_password(entry.encrypted_password), 'Updated-Password-456!')
        self.assertEqual(client.post(reverse('vault:delete_password', args=[entry.pk])).status_code, 200)
        self.assertFalse(PasswordEntry.objects.filter(pk=entry.pk).exists())

    def test_other_users_cannot_access_entries(self):
        entry = self.entry(user=self.other)
        client = self.signed_in()
        for name in ['edit_password', 'delete_password']:
            with self.subTest(action=name):
                self.assertEqual(client.post(reverse('vault:' + name, args=[entry.pk])).status_code, 404)
        self.assertTrue(PasswordEntry.objects.filter(pk=entry.pk).exists())

    def test_other_users_cannot_modify_categories(self):
        client = self.signed_in()
        for name in ['edit_category', 'delete_category']:
            with self.subTest(action=name):
                self.assertEqual(client.post(reverse('vault:' + name, args=[self.other_category.pk])).status_code, 404)

    def test_other_users_category_rejected(self):
        response = self.signed_in().post(reverse('vault:add_password'), {
            'website': 'example.test', 'password': 'Saved-Password-123!',
            'category': self.other_category.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PasswordEntry.objects.filter(user=self.user).exists())

    def test_category_crud(self):
        client = self.signed_in()
        self.assertEqual(client.post(reverse('vault:add_category'), {'name': 'Work'}).status_code, 302)
        category = Category.objects.get(user=self.user, name='Work')
        self.assertEqual(client.post(reverse('vault:edit_category', args=[category.pk]), {'name': 'Office'}).status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Office')
        self.assertEqual(client.post(reverse('vault:delete_category', args=[category.pk])).status_code, 200)
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_csrf_rejects_unprotected_write(self):
        response = self.signed_in(csrf=True).post(reverse('vault:add_category'), {'name': 'CSRF'})
        self.assertEqual(response.status_code, 403)

    def test_generator_options_and_bounds(self):
        for length in [8, 12, 32]:
            for _ in range(10):
                password = generate_password(length)
                self.assertEqual(len(password), length)
                self.assertTrue(any(c.isupper() for c in password))
                self.assertTrue(any(c.islower() for c in password))
                self.assertTrue(any(c.isdigit() for c in password))
                self.assertTrue(any(not c.isalnum() for c in password))
        for length in [7, 33]:
            with self.assertRaises(ValueError):
                generate_password(length)
        client = self.signed_in()
        self.assertEqual(client.post(reverse('vault:generate_password'), {'length': 'bad'}).status_code, 400)
        response = client.post(reverse('vault:check_strength'), {'password': 'short'})
        self.assertEqual(response.json()['strength'], 'weak')

    def test_settings_and_profile_update(self):
        client = self.signed_in()
        self.assertEqual(client.get(reverse('accounts:account_settings')).status_code, 200)
        self.assertEqual(client.post(reverse('accounts:account_settings'), {
            'update_profile': '1', 'first_name': 'Updated', 'last_name': 'Tester',
        }).status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

    def test_password_change(self):
        client = self.signed_in()
        new_password = 'Replacement-Strong-Password-652!'
        response = client.post(reverse('accounts:account_settings'), {
            'change_password': '1', 'old_password': self.password,
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertEqual(client.get(reverse('vault:dashboard')).status_code, 200)

    def test_2fa_requires_token_and_accepts_valid_token(self):
        self.user.is_2fa_enabled = True
        self.user.save()
        device = TOTPDevice.objects.create(user=self.user, name='validation', confirmed=True)
        response = self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.assertEqual(response.url, reverse('accounts:two_factor_verify'))
        self.assertNotIn('_auth_user_id', self.client.session)
        token = str(totp(device.bin_key)).zfill(6)
        self.client.post(reverse('accounts:two_factor_verify'), {'otp_token': token})
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_2fa_rejects_invalid_token(self):
        self.user.is_2fa_enabled = True
        self.user.save()
        TOTPDevice.objects.create(user=self.user, name='validation', confirmed=True)
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.client.post(reverse('accounts:two_factor_verify'), {'otp_token': 'not-a-token'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_completed_2fa_session_is_recognized_by_otp_middleware(self):
        self.user.is_2fa_enabled = True
        self.user.save()
        device = TOTPDevice.objects.create(user=self.user, name='validation', confirmed=True)
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.client.post(reverse('accounts:two_factor_verify'), {'otp_token': str(totp(device.bin_key)).zfill(6)})
        response = self.client.get(reverse('vault:dashboard'))
        self.assertTrue(response.wsgi_request.user.is_verified(),
                        'Custom OTP login does not record the verified device in the session.')

    def test_confirmed_device_requires_otp_even_with_stale_flag(self):
        client = self.signed_in()
        url = reverse('two_factor:setup')
        self.assertEqual(client.get(url).status_code, 200)
        response = client.post(url, {'setup_view-current_step': 'welcome'})
        self.assertEqual(response.context['wizard']['steps'].current, 'generator')
        qr = client.get(reverse('two_factor:qr'))
        self.assertEqual(qr.status_code, 200)
        self.assertTrue(qr['Content-Type'].startswith('image/'))
        token = str(totp(b32decode(response.context['secret_key']))).zfill(6)
        response = client.post(url, {'setup_view-current_step': 'generator', 'generator-token': token})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TOTPDevice.objects.filter(user=self.user, confirmed=True).exists())
        User.objects.filter(pk=self.user.pk).update(is_2fa_enabled=False)
        client.logout()
        client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.assertNotIn('_auth_user_id', client.session,
                         'Completing the package setup leaves the custom flag False, bypassing OTP on custom login.')

    def test_2fa_setup_does_not_enable_before_confirmation(self):
        response = self.signed_in().post(reverse('accounts:account_settings'), {
            'toggle_2fa': '1', 'is_2fa_enabled': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_2fa_enabled,
                         '2FA enabled before a confirmed device exists; abandoning setup blocks custom login.')

    def test_manage_2fa_page_renders(self):
        self.assertEqual(self.signed_in().get(reverse('accounts:manage_2fa')).status_code, 200)

    def test_2fa_setup_page_renders(self):
        self.assertEqual(self.signed_in().get(reverse('accounts:two_factor_setup')).status_code, 200)

    def recovery_code(self):
        raw = 'validation-recovery-code-123456'
        code = RecoveryCode(user=self.user, code=make_password(raw))
        code._raw_code = raw
        with contextlib.redirect_stdout(io.StringIO()):
            code.save()
        return raw, code

    def test_recovery_code_is_single_use(self):
        raw, code = self.recovery_code()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(code.get_raw_code(), raw)
        self.client.post(reverse('accounts:recovery_login'), {'email': self.user.email, 'code': raw})
        self.assertIn('_auth_user_id', self.client.session)
        code.refresh_from_db()
        self.assertTrue(code.is_used)
        client = Client()
        client.post(reverse('accounts:recovery_login'), {'email': self.user.email, 'code': raw})
        self.assertNotIn('_auth_user_id', client.session)

    def test_recovery_login_blocks_inactive_user(self):
        raw, code = self.recovery_code()
        self.user.is_active = False
        self.user.save()
        self.client.post(reverse('accounts:recovery_login'), {'email': self.user.email, 'code': raw})
        response = self.client.get(reverse('vault:dashboard'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 302)

    def test_recovery_key_not_printed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            get_fernet()
        self.assertFalse(bool(output.getvalue()), 'Recovery encryption key was printed to stdout.')

    def test_password_change_does_not_log_secrets(self):
        client = self.signed_in()
        with patch('logging.Logger.info') as log:
            client.post(reverse('accounts:account_settings'), {
                'change_password': '1', 'old_password': self.password,
                'new_password1': 'Replacement-Strong-Password-652!',
                'new_password2': 'Replacement-Strong-Password-652!',
            })
        self.assertFalse(any(self.password in str(call) for call in log.call_args_list),
                         'The old and new passwords were passed to the logger.')

    def test_database_alone_cannot_decrypt_password(self):
        entry = self.entry()
        self.assertNotIn('key', {field.name for field in entry._meta.fields})
        self.assertNotIn(b'Saved-Password-123!', bytes(entry.encrypted_password))
        self.assertEqual(decrypt_password(entry.encrypted_password), 'Saved-Password-123!')
        with self.assertRaises(Exception):
            Fernet(Fernet.generate_key()).decrypt(bytes(entry.encrypted_password))

    def test_dashboard_does_not_insert_password_as_html(self):
        template = engines['django'].get_template('vault/dashboard.html')
        source = template.template.source
        self.assertFalse(bool(re.search(r'innerHTML\s*=\s*isMasked', source)),
                         'Password values enter HTML through a template literal; use textContent/value.')

    def test_custom_login_rate_limit(self):
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': 'wrong'})
        response = self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': 'wrong'})
        self.assertEqual(response.status_code, 403)

    def test_account_deletion(self):
        entry = self.entry()
        self.assertEqual(self.signed_in().post(reverse('accounts:account_settings'), {
            'delete_account': '1', 'current_password': self.password,
        }).status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(PasswordEntry.objects.filter(pk=entry.pk).exists())

    def test_reveal_is_private_post_and_owner_only(self):
        entry = self.entry(password='<b>literal</b>"&-Secret-123!')
        url = reverse('vault:reveal_password', args=[entry.pk])
        client = self.signed_in()
        dashboard = client.get(reverse('vault:dashboard'))
        self.assertNotContains(dashboard, 'literal')
        self.assertIn('no-store', dashboard['Cache-Control'])
        self.assertEqual(client.get(url).status_code, 405)
        response = client.post(url)
        self.assertEqual(response.json()['password'], '<b>literal</b>"&-Secret-123!')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.signed_in(self.other).post(url).status_code, 404)
        self.assertEqual(self.signed_in(csrf=True).post(url).status_code, 403)

    def test_full_password_reset_and_token_reuse(self):
        import re
        self.client.post(reverse('accounts:password_reset'), {'email': self.user.email})
        url = re.search(r'http://testserver(/accounts/reset/[^\s]+)', mail.outbox[0].body).group(1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        new_password = 'Reset-Strong-Password-941!'
        response = self.client.post(response.url, {'new_password1': new_password, 'new_password2': new_password})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        client = Client()
        response = client.get(url, follow=True)
        self.assertContains(response, 'invalid', status_code=200)

    def test_verification_link_cannot_reset_password_or_be_reused(self):
        self.user.email_verified = False
        self.user.save()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        from django.contrib.auth.tokens import default_token_generator as password_tokens
        self.assertFalse(password_tokens.check_token(self.user, token))
        url = reverse('accounts:verify_email', args=[uid, token])
        self.client.get(url)
        self.user.refresh_from_db()
        self.assertFalse(default_token_generator.check_token(self.user, token))

    def test_destructive_settings_require_current_password(self):
        client = self.signed_in()
        client.post(reverse('accounts:account_settings'), {'delete_account': '1'})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_abandoned_setup_still_allows_password_login(self):
        client = self.signed_in()
        client.post(reverse('accounts:account_settings'), {'toggle_2fa': '1', 'is_2fa_enabled': 'on'})
        client.logout()
        client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.assertIn('_auth_user_id', client.session)

    def test_otp_challenge_expires_and_password_change_invalidates_it(self):
        TOTPDevice.objects.create(user=self.user, name='validation', confirmed=True)
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        session = self.client.session
        session['2fa_started'] = 0
        session.save()
        self.assertRedirects(self.client.get(reverse('accounts:two_factor_verify')), reverse('accounts:login'))
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': self.password})
        self.user.set_password('Changed-Password-722!')
        self.user.save()
        self.assertRedirects(self.client.get(reverse('accounts:two_factor_verify')), reverse('accounts:login'))

    def test_recovery_codes_are_displayed_once_and_regeneration_requires_password(self):
        client = self.signed_in()
        url = reverse('accounts:two_factor_setup')
        client.get(url)
        response = client.post(url, {'setup_view-current_step': 'welcome'})
        token = str(totp(b32decode(response.context['secret_key']))).zfill(6)
        response = client.post(url, {'setup_view-current_step': 'generator', 'generator-token': token})
        self.assertEqual(response.status_code, 302)
        raw_codes = client.session['new_recovery_codes']
        self.assertEqual(len(raw_codes), 10)
        response = client.get(reverse('accounts:account_settings'))
        self.assertContains(response, raw_codes[0])
        self.assertNotContains(client.get(reverse('accounts:account_settings')), raw_codes[0])
        ids = list(RecoveryCode.objects.filter(user=self.user).values_list('pk', flat=True))
        client.post(reverse('accounts:account_settings'), {'regenerate_codes': '1'})
        self.assertEqual(list(RecoveryCode.objects.filter(user=self.user).values_list('pk', flat=True)), ids)
        client.post(reverse('accounts:account_settings'), {'regenerate_codes': '1', 'current_password': self.password})
        self.assertFalse(RecoveryCode.objects.filter(pk__in=ids).exists())
        self.assertEqual(len(client.session['new_recovery_codes']), 10)
        client.post(reverse('accounts:account_settings'), {'toggle_2fa': '1', 'current_password': self.password})
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(RecoveryCode.objects.filter(user=self.user).exists())

    def test_alternate_login_requires_otp(self):
        device = TOTPDevice.objects.create(user=self.user, name='validation', confirmed=True)
        response = self.client.post(reverse('two_factor:login'), {
            'email': self.user.email, 'password': self.password})
        self.assertEqual(response.url, reverse('accounts:two_factor_verify'))
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(response.url, {'otp_token': str(totp(device.bin_key)).zfill(6)})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.get(reverse('vault:dashboard')).wsgi_request.user.is_verified())

    def test_rate_limit_survives_cache_reset_and_other_client(self):
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': 'wrong'})
        cache.clear()
        self.assertEqual(Client().post(reverse('accounts:login'), {'email': self.user.email, 'password': 'wrong'}).status_code, 403)

    def test_existing_session_cannot_skip_new_otp_enrollment(self):
        client = self.signed_in()
        TOTPDevice.objects.create(user=self.user, name='validation', confirmed=True)
        response = client.get(reverse('vault:dashboard'))
        self.assertEqual(response.url, reverse('accounts:two_factor_verify'))
        self.assertNotIn('_auth_user_id', client.session)

    def test_weak_password_rejected_and_failed_registration_mail_rolls_back(self):
        data = {'email': 'mailfail@example.test', 'first_name': 'Mail', 'last_name': 'Test',
                'password1': '123', 'password2': '123'}
        self.client.post(reverse('accounts:register'), data)
        self.assertFalse(User.objects.filter(email=data['email']).exists())
        data.update(password1=self.password, password2=self.password)
        with patch('accounts.views.send_mail', side_effect=OSError('offline')):
            response = self.client.post(reverse('accounts:register'), data)
        self.assertContains(response, 'Email could not be sent')
        self.assertFalse(User.objects.filter(email=data['email']).exists())

    def test_login_email_is_case_insensitive(self):
        self.client.post(reverse('accounts:login'), {'email': self.user.email.upper(), 'password': self.password})
        self.assertIn('_auth_user_id', self.client.session)

    def test_password_whitespace_is_preserved(self):
        password = '  Whitespace-Password-912!  '
        self.user.set_password(password)
        self.user.save()
        self.client.post(reverse('accounts:login'), {'email': self.user.email, 'password': password})
        self.assertIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('vault:add_password'), {
            'website': 'spaces.test', 'username': 'tester', 'password': password,
        })
        self.assertEqual(response.status_code, 302)
        entry = PasswordEntry.objects.get(user=self.user)
        self.assertEqual(decrypt_password(entry.encrypted_password), password)
        new_password = '  New-Whitespace-Password-551!  '
        response = self.client.post(reverse('accounts:account_settings'), {
            'change_password': '1', 'old_password': password,
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_registration_rejects_case_insensitive_duplicate_email(self):
        response = self.client.post(reverse('accounts:register'), {
            'email': self.user.email.upper(), 'first_name': 'Alice', 'last_name': 'Tester',
            'password1': self.password, 'password2': self.password,
        })
        self.assertContains(response, 'An account with this email already exists.')
        self.assertEqual(User.objects.filter(email__iexact=self.user.email).count(), 1)

    @override_settings(RECOVERY_CODE_KEY='invalid')
    def test_invalid_recovery_key_fails_instead_of_generating_ephemeral_key(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            get_fernet()
