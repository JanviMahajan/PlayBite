from django.db import models
from django.utils.translation import gettext_lazy as _

from playbite.models import TimeStampedModel


class Customer(TimeStampedModel):
    full_name = models.CharField(_('full name'), max_length=255)
    phone_number = models.CharField(_('phone number'), max_length=32, unique=True, db_index=True)
    whatsapp_number = models.CharField(_('WhatsApp number'), max_length=32, blank=True, null=True)
    total_visits = models.PositiveIntegerField(_('total visits'), default=0)

    class Meta:
        verbose_name = _('customer')
        verbose_name_plural = _('customers')
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.phone_number})'
