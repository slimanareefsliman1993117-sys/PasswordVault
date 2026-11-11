from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0008_email_verified')]
    operations = [migrations.CreateModel(
        name='RateLimitBucket',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('key', models.CharField(max_length=64, unique=True)),
            ('count', models.PositiveIntegerField(default=0)),
            ('expires_at', models.BigIntegerField(db_index=True)),
        ],
    )]
