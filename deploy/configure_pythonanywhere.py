"""Initialize a NEW PythonAnywhere installation without uploading local secrets."""
import argparse
from pathlib import Path
import re
import secrets

from cryptography.fernet import Fernet

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--domain', required=True, help='Exact web app hostname, without https:// or a path')
parser.add_argument('--console-email', action='store_true', help='Use server-output mail for testing only')
args = parser.parse_args()
domain = args.domain.strip().lower()
if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
    parser.error('--domain must be a hostname such as username.pythonanywhere.com')
root = Path(__file__).resolve().parent.parent
env_file = root / '.env'
# Never regenerate keys or overwrite an existing site's environment.
try:
    handle = env_file.open('x')
except FileExistsError:
    raise SystemExit('Existing .env preserved. Review its deployment configuration manually; keys were not changed.')
with handle:
    env_file.chmod(0o600)
    values = {
        'SECRET_KEY': secrets.token_urlsafe(64),
        'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'RECOVERY_CODE_KEY': Fernet.generate_key().decode(),
        'DEBUG': 'False',
        'ALLOWED_HOSTS': domain,
        'CSRF_TRUSTED_ORIGINS': 'https://' + domain,
        'TRUST_PROXY_HEADERS': 'False',
        'EMAIL_BACKEND': ('django.core.mail.backends.console.EmailBackend' if args.console_email
                          else 'django.core.mail.backends.smtp.EmailBackend'),
        'EMAIL_HOST': 'smtp.gmail.com',
        'EMAIL_PORT': '587',
        'EMAIL_USE_TLS': 'True',
        'EMAIL_HOST_USER': '',
        'EMAIL_HOST_PASSWORD': '',
        'DEFAULT_FROM_EMAIL': '',
    }
    for name, value in values.items():
        handle.write(f'{name}={value}\n')

wsgi = root / 'deploy' / 'wsgi.generated.py'
wsgi.write_text(f'''# Generated for this installation. Copy into the Web tab's WSGI file.
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project = Path({str(root)!r})
sys.path.insert(0, str(project))
load_dotenv(project / '.env')
os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
from django.core.wsgi import get_wsgi_application
from django.conf import settings
application = get_wsgi_application()
if settings.DEBUG:
    raise RuntimeError('This production WSGI configuration requires DEBUG=False.')
''')
print(f'Created private .env for {domain}; no key values were printed.')
print(f'WSGI configuration: {wsgi}')
if args.console_email:
    print('Mail is in TEST mode: verification/reset links go to server output, not inboxes.')
else:
    print('Set EMAIL_HOST_USER, EMAIL_HOST_PASSWORD and DEFAULT_FROM_EMAIL privately before opening registration.')
