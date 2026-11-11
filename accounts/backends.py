from django.contrib.auth.backends import ModelBackend


class VerifiedEmailBackend(ModelBackend):
    """Apply the same account policy to every authentication entry point."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and user.email_verified
