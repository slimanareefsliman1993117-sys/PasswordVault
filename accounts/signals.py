from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import User


@receiver(post_save, sender=TOTPDevice)
@receiver(post_delete, sender=TOTPDevice)
def synchronize_2fa_status(sender, instance, **kwargs):
    enabled = TOTPDevice.objects.filter(user_id=instance.user_id, confirmed=True).exists()
    User.objects.filter(pk=instance.user_id).update(is_2fa_enabled=enabled)
