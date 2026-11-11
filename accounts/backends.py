from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.utils.crypto import constant_time_compare

from .demo import DEMO_EMAIL, get_demo_user


class VerifiedEmailBackend(ModelBackend):
    """Apply the same account policy to every authentication entry point."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email', username)
        if email and email.strip().casefold() == DEMO_EMAIL:
            demo = get_demo_user()
            if demo and not demo.has_usable_password():
                if (settings.PUBLIC_DEMO_PASSWORD and password is not None
                        and request and request.resolver_match
                        and request.resolver_match.view_name in {'accounts:login', 'two_factor:login'}
                        and constant_time_compare(password, settings.PUBLIC_DEMO_PASSWORD)):
                    return demo
                return None
        return super().authenticate(request, username=username, password=password, **kwargs)

    def user_can_authenticate(self, user):
        if user.is_public_demo:
            return bool(settings.PUBLIC_DEMO_PASSWORD and user.is_active and user.email_verified
                        and not user.is_staff and not user.is_superuser and not user.has_usable_password())
        return super().user_can_authenticate(user) and user.email_verified
