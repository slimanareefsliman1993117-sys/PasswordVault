from django.core.management.base import BaseCommand, CommandError

from accounts.demo import DEMO_EMAIL, DEMO_USERNAME
from accounts.models import User


class Command(BaseCommand):
    help = 'Prepare the dedicated public demo login for Password Vault.'

    def handle(self, *args, **options):
        existing = User.objects.filter(email__iexact=DEMO_EMAIL).first()
        if existing:
            if (not existing.is_public_demo or existing.is_staff or existing.is_superuser
                    or existing.has_usable_password() or not existing.is_active or not existing.email_verified):
                raise CommandError('The demo address is already in use by another account.')
            self.stdout.write('Public demo login already exists.')
            return
        User.objects.create_user(
            email=DEMO_EMAIL,
            username=DEMO_USERNAME,
            first_name='Demo',
            last_name='Visitor',
            email_verified=True,
        )
        self.stdout.write(self.style.SUCCESS('Public demo login prepared.'))
