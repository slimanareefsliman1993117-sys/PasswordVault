"""Isolated validation settings: synthetic secrets, no SMTP, temporary database."""
import os
from cryptography.fernet import Fernet

for name, value in {
    'SECRET_KEY': 'validation-only-' + 'x' * 64,
    'EMAIL_HOST_USER': 'validation@example.test',
    'EMAIL_HOST_PASSWORD': 'validation-only',
    'ENCRYPTION_KEY': Fernet.generate_key().decode(),
    'RECOVERY_CODE_KEY': Fernet.generate_key().decode(),
}.items():
    os.environ[name] = value

from password_manager.settings import *  # noqa: E402,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null']},
}


DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
