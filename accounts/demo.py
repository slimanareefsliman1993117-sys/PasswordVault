DEMO_EMAIL = 'demo@passwordvault.example'
DEMO_USERNAME = 'public-vault-demo'


def get_demo_user():
    from .models import User

    return User.objects.filter(
        email__iexact=DEMO_EMAIL,
        username=DEMO_USERNAME,
        is_active=True,
        email_verified=True,
        is_staff=False,
        is_superuser=False,
    ).first()
