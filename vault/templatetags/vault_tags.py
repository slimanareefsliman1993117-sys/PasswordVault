from django import template
from ..utils import decrypt_password as decrypt

register = template.Library()

@register.filter
def decrypt_password(entry):
    return decrypt(entry.encrypted_password)
