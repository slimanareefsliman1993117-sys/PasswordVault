import secrets
import time
from smtplib import SMTPException
from anymail.exceptions import AnymailError

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from .ratelimit import ratelimit
from two_factor.views import SetupView

from .forms import CustomUserCreationForm, LoginForm, ProfileUpdateForm, CustomPasswordChangeForm
from .models import RecoveryCode, User
from .tokens import email_verification_token


def send_verification(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    url = request.build_absolute_uri(reverse('accounts:verify_email', args=[
        uid, email_verification_token.make_token(user)]))
    body = render_to_string('accounts/email_verification.html', {'user': user, 'verify_url': url})
    send_mail('Verify your Password Vault email', body, settings.DEFAULT_FROM_EMAIL,
              [user.email], html_message=body)


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@sensitive_post_parameters('password1', 'password2')
@require_http_methods(['GET', 'POST'])
def register(request):
    form = CustomUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                send_verification(request, user)
        except (SMTPException, OSError, AnymailError):
            form.add_error(None, 'Email could not be sent. Please try again later.')
        else:
            return render(request, 'accounts/register_success.html', {'email': user.email})
    return render(request, 'accounts/register.html', {'form': form})


def begin_challenge(request, user):
    # Bind a short-lived challenge to the password that was just authenticated.
    logout(request)
    request.session['2fa_user_id'] = user.pk
    request.session['2fa_auth_hash'] = user.get_session_auth_hash()
    request.session['2fa_started'] = time.time()
    request.session['2fa_attempts'] = 0


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('vault:dashboard')
    form = LoginForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, email=form.cleaned_data['email'], password=form.cleaned_data['password'])
        if user:
            if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
                begin_challenge(request, user)
                return redirect('accounts:two_factor_verify')
            login(request, user)
            return redirect('vault:dashboard')
        error = 'Invalid credentials, or your email has not been verified.'
    return render(request, 'accounts/login.html', {'form': form, 'error': error})


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@sensitive_post_parameters('otp_token')
@require_http_methods(['GET', 'POST'])
def two_factor_verify(request):
    user = User.objects.filter(pk=request.session.get('2fa_user_id'), is_active=True, email_verified=True).first()
    valid_challenge = (user is not None
                       and time.time() - request.session.get('2fa_started', 0) < 300
                       and request.session.get('2fa_attempts', 0) < 5
                       and constant_time_compare(request.session.get('2fa_auth_hash', ''), user.get_session_auth_hash()))
    if not valid_challenge:
        request.session.flush()
        return redirect('accounts:login')
    error = None
    if request.method == 'POST':
        request.session['2fa_attempts'] = request.session.get('2fa_attempts', 0) + 1
        with transaction.atomic():
            for device in TOTPDevice.objects.select_for_update().filter(user=user, confirmed=True):
                if device.verify_token(request.POST.get('otp_token', '')):
                    login(request, user, backend='accounts.backends.VerifiedEmailBackend')
                    otp_login(request, device)
                    for key in ['2fa_user_id', '2fa_auth_hash', '2fa_started', '2fa_attempts']:
                        request.session.pop(key, None)
                    return redirect('vault:dashboard')
        error = 'Invalid code. Wait a moment before trying again.'
    return render(request, 'accounts/two_factor_verify.html', {'error': error})


def generate_recovery_codes(user):
    codes = [secrets.token_hex(16) for _ in range(10)]
    with transaction.atomic():
        RecoveryCode.objects.filter(user=user).delete()
        for raw in codes:
            code = RecoveryCode(user=user, code=make_password(raw))
            code._raw_code = raw
            code.save()
    return codes


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@sensitive_post_parameters('code')
@require_http_methods(['GET', 'POST'])
def recovery_login(request):
    error = None
    if request.method == 'POST':
        user = User.objects.filter(email=request.POST.get('email', ''), is_active=True, email_verified=True).first()
        if user:
            for candidate in RecoveryCode.objects.filter(user=user, is_used=False):
                if check_password(request.POST.get('code', ''), candidate.code):
                    # Conditional update makes a code single-use across concurrent requests.
                    if RecoveryCode.objects.filter(pk=candidate.pk, is_used=False).update(is_used=True):
                        request.session.flush()
                        login(request, user, backend='accounts.backends.VerifiedEmailBackend')
                        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
                        if device:
                            otp_login(request, device)
                        messages.success(request, 'Recovery code accepted. Save new codes if needed.')
                        return redirect('vault:dashboard')
        error = 'Invalid recovery code or email.'
    return render(request, 'accounts/recovery_login.html', {'error': error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@require_http_methods(['GET'])
def verify_email(request, uidb64, token):
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode())
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
        user = None
    if user and email_verification_token.check_token(user, token):
        User.objects.filter(pk=user.pk).update(email_verified=True)
        return render(request, 'accounts/verify_success.html')
    return render(request, 'accounts/verify_error.html', {'error': 'Invalid or expired verification link.'})


@ratelimit(key='ip', rate='3/m', method='POST', block=True)
@require_http_methods(['GET', 'POST'])
def resend_verification(request):
    context = {}
    if request.method == 'POST':
        user = User.objects.filter(email=request.POST.get('email', ''), email_verified=False, is_active=True).first()
        try:
            if user:
                send_verification(request, user)
        except (SMTPException, OSError, AnymailError):
            context['resend_error'] = 'Email service is unavailable. Please try again later.'
        else:
            context['resend_success'] = 'If this account needs verification, an email has been sent.'
    return render(request, 'accounts/verify_error.html', context)


@login_required
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@sensitive_post_parameters('current_password', 'old_password', 'new_password1', 'new_password2')
@require_http_methods(['GET', 'POST'])
def account_settings(request):
    user = request.user
    has_2fa = TOTPDevice.objects.filter(user=user, confirmed=True).exists()
    profile_form = ProfileUpdateForm(instance=user)
    password_form = CustomPasswordChangeForm(user=user)
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('accounts:account_settings')
        elif 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed.')
                return redirect('accounts:account_settings')
        elif 'toggle_2fa' in request.POST:
            enabled = request.POST.get('is_2fa_enabled') == 'on'
            if enabled and not has_2fa:
                return redirect('accounts:two_factor_setup')
            if not enabled and has_2fa:
                if not user.check_password(request.POST.get('current_password', '')):
                    messages.error(request, 'Enter your current password to disable 2FA.')
                else:
                    with transaction.atomic():
                        TOTPDevice.objects.filter(user=user).delete()
                        RecoveryCode.objects.filter(user=user).delete()
                    request.session.pop('otp_device_id', None)
                    messages.success(request, '2FA disabled.')
                return redirect('accounts:account_settings')
        elif 'regenerate_codes' in request.POST:
            if not has_2fa or not user.check_password(request.POST.get('current_password', '')):
                messages.error(request, 'Enable 2FA and enter your current password to regenerate codes.')
            else:
                request.session['new_recovery_codes'] = generate_recovery_codes(user)
            return redirect('accounts:account_settings')
        elif 'delete_account' in request.POST:
            if user.check_password(request.POST.get('current_password', '')):
                user.delete()
                logout(request)
                return redirect('accounts:login')
            messages.error(request, 'Enter your current password to delete your account.')
        elif 'clear_recovery_codes' in request.POST:
            request.session.pop('new_recovery_codes', None)
            return redirect('accounts:account_settings')
    codes = request.session.pop('new_recovery_codes', [])
    return render(request, 'accounts/account_settings.html', {
        'profile_form': profile_form, 'password_form': password_form,
        'has_2fa': has_2fa, 'new_recovery_codes': codes,
        'recovery_code_count': RecoveryCode.objects.filter(user=user, is_used=False).count(),
        'user_email': user.email,
    })


@login_required
def manage_2fa(request):
    return account_settings(request)


@method_decorator([login_required], name='dispatch')
class VaultSetupView(SetupView):
    template_name = 'two_factor/core/setup.html'

    def get_prefix(self, request, *args, **kwargs):
        return 'setup_view'

    def get_success_url(self):
        return reverse('accounts:account_settings')

    def done(self, form_list, **kwargs):
        with transaction.atomic():
            response = super().done(form_list, **kwargs)
            self.request.session['new_recovery_codes'] = generate_recovery_codes(self.request.user)
        return response


@method_decorator(ratelimit(key='ip', rate='3/m', method='POST', block=True), name='dispatch')
class VaultPasswordResetView(PasswordResetView):
    pass

