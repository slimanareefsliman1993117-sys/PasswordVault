"""Environment-driven settings. Use DEBUG=true for local HTTP development."""
from pathlib import Path
from cryptography.fernet import Fernet
from decouple import config
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,[::1]',
                       cast=lambda value: [host.strip() for host in value.split(',') if host.strip()])
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='',
                            cast=lambda value: [origin.strip() for origin in value.split(',') if origin.strip()])
ENCRYPTION_KEY = config('ENCRYPTION_KEY')
RECOVERY_CODE_KEY = config('RECOVERY_CODE_KEY')
for name in ('ENCRYPTION_KEY', 'RECOVERY_CODE_KEY'):
    try:
        Fernet(globals()[name].encode())
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(f'{name} must be a persistent Fernet key.') from exc

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'django_otp', 'django_otp.plugins.otp_totp', 'django_otp.plugins.otp_static',
    'two_factor', 'accounts.apps.AccountsConfig', 'vault', 'api', 'widget_tweaks',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'accounts.middleware.VaultSessionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'password_manager.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'password_manager.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': BASE_DIR / 'db.sqlite3', 'OPTIONS': {'timeout': 20}}}
AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.VerifiedEmailBackend']
PUBLIC_DEMO_PASSWORD = config('PUBLIC_DEMO_PASSWORD', default='')
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
EMAIL_BACKEND = config('EMAIL_BACKEND', default=(
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'))
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='') or EMAIL_HOST_USER or 'vault@localhost'
EMAIL_TIMEOUT = 15
# Mailjet uses HTTPS, including PythonAnywhere's proxy for free accounts.
# Keep the key private in .env and leave SMTP available as an alternative backend.
ANYMAIL = {
    'MAILJET_API_KEY': config('MAILJET_API_KEY', default=''),
    'MAILJET_SECRET_KEY': config('MAILJET_SECRET_KEY', default=''),
    'REQUESTS_TIMEOUT': EMAIL_TIMEOUT,
    'SEND_DEFAULTS': {'track_clicks': False, 'track_opens': False},
}
if EMAIL_BACKEND == 'anymail.backends.mailjet.EmailBackend':
    if not all(ANYMAIL[key] for key in ('MAILJET_API_KEY', 'MAILJET_SECRET_KEY')):
        raise ImproperlyConfigured('MAILJET_API_KEY and MAILJET_SECRET_KEY are required for Mailjet delivery.')
    if not config('DEFAULT_FROM_EMAIL', default=''):
        raise ImproperlyConfigured('DEFAULT_FROM_EMAIL must be a verified Mailjet sender.')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'vault:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'
TWO_FACTOR_PATCH_ADMIN = False
OTP_TOTP_ISSUER = 'Password Vault'
TWO_FACTOR_LOGIN_TIMEOUT = 300
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
PASSWORD_RESET_TIMEOUT = 3600
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'root': {'handlers': ['console'], 'level': 'WARNING'}}

if not DEBUG:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
if config('TRUST_PROXY_HEADERS', default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
