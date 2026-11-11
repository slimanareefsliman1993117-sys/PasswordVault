from django.db import migrations, models
from django.db.models.functions import Lower


def normalize_emails(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    users = list(User.objects.using(schema_editor.connection.alias).all())
    emails = [user.email.strip().lower() for user in users]
    if len(emails) != len(set(emails)):
        raise RuntimeError('Resolve duplicate email addresses differing only in case before migrating.')
    for user, email in zip(users, emails):
        User.objects.using(schema_editor.connection.alias).filter(pk=user.pk).update(email=email)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0009_ratelimitbucket')]
    operations = [
        migrations.RunPython(normalize_emails, migrations.RunPython.noop),
        migrations.AddConstraint('user', models.UniqueConstraint(Lower('email'), name='accounts_email_case_insensitive')),
    ]
