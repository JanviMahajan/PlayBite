from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Restaurant, RestaurantTable


@receiver(post_save, sender=Restaurant)
def ensure_default_reward(sender, instance, created, **kwargs):
    if created:
        from coupons.services.defaults import ensure_default_tap_reward
        ensure_default_tap_reward(instance)


@receiver(post_save, sender=RestaurantTable)
def ensure_qr_generated(sender, instance, created, **kwargs):
    # Generate QR image on creation or when missing
    try:
        if created or not instance.qr_image:
            instance.generate_qr_image()
    except Exception:
        # Avoid breaking table creation if QR libraries are not installed
        pass
