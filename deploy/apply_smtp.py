"""Apply a private SMTP transfer file without changing application encryption keys."""
import argparse
import json
import os
from pathlib import Path
import smtplib
import sys
import tempfile

from dotenv import dotenv_values, set_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    env = root / '.env'
    source = args.config.resolve()
    source.chmod(0o600)
    incoming = json.loads(source.read_text())
    allowed = {
        'EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USE_TLS',
        'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL',
    }
    if set(incoming) != allowed:
        raise ValueError('Unexpected or missing configuration keys.')
    if incoming['EMAIL_BACKEND'] != 'django.core.mail.backends.smtp.EmailBackend':
        raise ValueError('SMTP backend required.')
    if str(incoming['EMAIL_USE_TLS']).lower() != 'true':
        raise ValueError('Verified STARTTLS is required.')
    if not incoming['EMAIL_HOST_USER'] or not incoming['EMAIL_HOST_PASSWORD']:
        raise ValueError('SMTP credentials are missing.')
    before = dotenv_values(env)
    protected = ['SECRET_KEY', 'ENCRYPTION_KEY', 'RECOVERY_CODE_KEY']
    if not all(before.get(key) for key in protected):
        raise ValueError('The existing application keys must be present.')
    descriptor, name = tempfile.mkstemp(prefix='.env.smtp-', dir=root)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(env.read_text())
        for key, value in incoming.items():
            set_key(temporary, key, str(value), quote_mode='always')
        after = dotenv_values(temporary)
        if any(before[key] != after[key] for key in protected):
            raise ValueError('Application key preservation check failed.')
        temporary.chmod(0o600)
        temporary.replace(env)
    finally:
        temporary.unlink(missing_ok=True)
    source.unlink()

    # Verify connectivity and authentication without transmitting a message.
    sys.path.insert(0, str(root))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
    import django
    django.setup()
    from django.core.mail import get_connection
    result = {'configuration_applied': True, 'application_keys_preserved': True,
              'temporary_transfer_removed': True, 'message_sent': False}
    try:
        with get_connection(fail_silently=False):
            pass
    except Exception as error:
        result.update(authentication='failed', error_type=type(error).__name__)
        if isinstance(error, smtplib.SMTPResponseException):
            result['smtp_code'] = error.smtp_code
        (root / 'deploy' / 'smtp-status.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 1
    result.update(authentication='passed', starttls=True)
    (root / 'deploy' / 'smtp-status.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
