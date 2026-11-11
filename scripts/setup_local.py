"""Create a local .env only when absent; never replace existing encryption keys."""
from pathlib import Path
import secrets
from cryptography.fernet import Fernet

path = Path(__file__).resolve().parent.parent / '.env'
try:
    with path.open('x') as file:
        path.chmod(0o600)
        file.write(f'SECRET_KEY={secrets.token_urlsafe(64)}\n')
        file.write(f'ENCRYPTION_KEY={Fernet.generate_key().decode()}\n')
        file.write(f'RECOVERY_CODE_KEY={Fernet.generate_key().decode()}\n')
        file.write('DEBUG=True\nALLOWED_HOSTS=localhost,127.0.0.1,[::1]\n')
        file.write('EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend\n')
except FileExistsError:
    print('Existing .env preserved. Encryption keys were not changed.')
else:
    print('Created .env with persistent keys. Back it up privately with your database.')
