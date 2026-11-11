from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import resolve, Resolver404, reverse
from django_otp.plugins.otp_totp.models import TOTPDevice


class VaultSessionMiddleware:
    """Require OTP for enrolled accounts, including sessions created before setup."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        request.is_public_demo = user.is_authenticated and user.is_public_demo
        if request.is_public_demo:
            try:
                view = resolve(request.path_info).view_name
            except Resolver404:
                view = None
            read_page = request.method in {'GET', 'HEAD'} and view in {
                'home', 'privacy', 'vault:dashboard', 'accounts:login', 'two_factor:login',
            }
            read_or_logout = request.method == 'POST' and view in {'vault:reveal_password', 'accounts:logout'}
            if not (read_page or read_or_logout):
                return HttpResponseForbidden('The public demo is read-only.', headers={'Cache-Control': 'private, no-store'})
        elif user.is_authenticated:
            if not user.is_active or not user.email_verified:
                logout(request)
                return redirect('accounts:login')
            exempt = {reverse('accounts:logout'), reverse('accounts:two_factor_verify'),
                      reverse('accounts:recovery_login')}
            if (request.path not in exempt
                    and TOTPDevice.objects.filter(user=user, confirmed=True).exists()
                    and not user.is_verified()):
                from .views import begin_challenge
                begin_challenge(request, user)
                return redirect('accounts:two_factor_verify')
        response = self.get_response(request)
        response['Cache-Control'] = 'private, no-store'
        response['Pragma'] = 'no-cache'
        return response
