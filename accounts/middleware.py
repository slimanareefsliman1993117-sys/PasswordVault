from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice


class VaultSessionMiddleware:
    """Require OTP for enrolled accounts, including sessions created before setup."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
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
