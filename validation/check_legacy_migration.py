"""Prove legacy ciphertext survives the schema/key migration on an isolated DB."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['DJANGO_SETTINGS_MODULE'] = 'validation.settings'
import django
django.setup()
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

executor = MigrationExecutor(connection)
old_targets = [('accounts', '0007_alter_user_managers'), ('vault', '0001_initial')]
executor.migrate(old_targets)
old_apps = executor.loader.project_state(old_targets).apps
User = old_apps.get_model('accounts', 'User')
Entry = old_apps.get_model('vault', 'PasswordEntry')
user = User.objects.create(email='legacy@example.test', password='test-hash', is_verified=True)
legacy_key = Fernet.generate_key()
plaintext = b'Legacy <password> with "quotes" & unicode-safe bytes'
entry = Entry.objects.create(user_id=user.pk, website='legacy.test',
                             encrypted_password=Fernet(legacy_key).encrypt(plaintext), key=legacy_key)
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
from accounts.models import User as CurrentUser
from vault.models import PasswordEntry
current = PasswordEntry.objects.get(pk=entry.pk)
assert CurrentUser.objects.get(pk=user.pk).email_verified is True
assert Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(bytes(current.encrypted_password)) == plaintext
assert 'key' not in {field.name for field in PasswordEntry._meta.fields}
try:
    Fernet(legacy_key).decrypt(bytes(current.encrypted_password))
except Exception:
    pass
else:
    raise AssertionError('Migrated data still decrypts with the discarded legacy key')
print('PASS: legacy password and email verification preserved; stored key removed.')
