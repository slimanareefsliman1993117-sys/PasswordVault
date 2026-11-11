"""Re-encrypt legacy rows before removing database-resident key material."""
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations


def reencrypt(apps, schema_editor):
    Entry = apps.get_model('vault', 'PasswordEntry')
    destination = Fernet(settings.ENCRYPTION_KEY.encode())
    for entry in Entry.objects.using(schema_editor.connection.alias).all().iterator():
        plaintext = Fernet(bytes(entry.key)).decrypt(bytes(entry.encrypted_password))
        entry.encrypted_password = destination.encrypt(plaintext)
        entry.save(using=schema_editor.connection.alias, update_fields=['encrypted_password'])


class Migration(migrations.Migration):
    atomic = True
    dependencies = [('vault', '0001_initial')]
    operations = [migrations.RunPython(reencrypt), migrations.RemoveField('passwordentry', 'key')]
