# Password Vault

A Django password manager with email verification, an encrypted personal vault,
authenticator-based two-factor authentication and single-use recovery codes.

Python 3.11 · Django 5.2 · SQLite · Fernet encryption

## Features

- Verified-email sign-in, password reset and account settings.
- Authenticator enrollment, OTP login and recovery codes.
- Encrypted password entries organized into categories, with search and filtering.
- Password generation, strength feedback and authorized show/copy actions.
- CSRF-protected changes, ownership checks and database-backed request limits.
- Local static assets and production HTTPS/cookie settings.

## Local setup

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/setup_local.py
python manage.py migrate
python manage.py runserver 127.0.0.1:8010
```

Open `http://127.0.0.1:8010/accounts/register/` to create an account. A new local
installation uses console email: verification and password-reset links appear
in the development server's terminal. Verify the email before signing in.
No default account or password is provided.

The setup script creates `.env` only if it is absent. It generates persistent
`SECRET_KEY`, `ENCRYPTION_KEY` and `RECOVERY_CODE_KEY` values. **Back up `.env`
privately together with the database.** Do not replace encryption keys on an
existing installation: stored passwords and recovery codes depend on them.

## Email delivery

SMTP and Mailjet HTTPS delivery are supported. Configure credentials privately
in `.env`; `.env.example` lists the available settings. The chosen provider must
permit sending and verify the sender. Including an email adapter in the source
does not establish that a particular provider account can deliver messages.

See [SETUP.txt](SETUP.txt) for email configuration, backups, migrations and production.

## Validation

```sh
.venv/bin/python validation/run.py test validation accounts vault api --verbosity 2
.venv/bin/python validation/check_legacy_migration.py
npm ci --prefix validation
npm test --prefix validation
```

The isolated Django runner uses synthetic secrets, an in-memory database and a
test email backend. Mailjet integration tests mock provider requests. Node.js is
required only for the JavaScript tests. The GitHub source snapshot passed **52
Django tests, 6 JavaScript tests and the legacy-data migration proof** before upload.
See [validation/REPORT.txt](validation/REPORT.txt) for the earlier dated repair
review; detailed local logs and historical baseline output are excluded from Git.

## PythonAnywhere deployment

Follow [deploy/PYTHONANYWHERE.txt](deploy/PYTHONANYWHERE.txt). Build an upload with:

```sh
.venv/bin/python deploy/build_package.py
```

For a fresh installation, the deployment helper generates private configuration
and a WSGI entry point. It refuses to overwrite an existing `.env`. Collect static
files and enable HTTPS before making the deployment available to users.

The repository excludes local credentials, encryption keys, databases, mail
diagnostics, generated WSGI files, virtual environments and private preview data.
