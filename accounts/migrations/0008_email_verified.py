from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_alter_user_managers')]
    operations = [migrations.RenameField('user', 'is_verified', 'email_verified')]
