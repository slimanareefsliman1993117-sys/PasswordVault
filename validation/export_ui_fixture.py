"""Render real templates with synthetic data for the JavaScript DOM tests."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['DJANGO_SETTINGS_MODULE'] = 'validation.settings'
import django
django.setup()
from django.core.management import call_command
from django.test import Client
from accounts.models import User
from vault.models import Category, PasswordEntry
from vault.utils import encrypt_password
call_command('migrate', verbosity=0)
user = User.objects.create_user(email='ui@example.test', password='Synthetic-Only-Password-124!', email_verified=True)
category = Category.objects.create(user=user, name='Personal')
PasswordEntry.objects.create(user=user, website='example.test', username='demo', category=category,
                             encrypted_password=encrypt_password('Synthetic-Only-Saved-Password-912!'))
client = Client()
client.force_login(user)
print(json.dumps({'dashboard': client.get('/vault/').content.decode(),
                  'form': client.get('/vault/add/').content.decode()}))
