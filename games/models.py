from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

from playbite.models import TimeStampedModel


class Game(TimeStampedModel):
    class Difficulty(models.TextChoices):
        EASY = 'easy', _('Easy')
        MEDIUM = 'medium', _('Medium')
        HARD = 'hard', _('Hard')

    name = models.CharField(_('name'), max_length=255)
    slug = models.SlugField(_('slug'), max_length=255, unique=True)
    description = models.TextField(_('description'), blank=True)
    difficulty = models.CharField(
        _('difficulty'),
        max_length=16,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    duration = models.DurationField(_('duration'))
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('game')
        verbose_name_plural = _('games')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Gameplay(TimeStampedModel):
    class Result(models.TextChoices):
        ASSIGNED = 'assigned', _('Assigned')
        IN_PROGRESS = 'in_progress', _('In progress')
        WON = 'won', _('Won')
        LOST = 'lost', _('Lost')

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        'customer.Customer',
        on_delete=models.CASCADE,
        related_name='gameplays',
        verbose_name=_('customer'),
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='gameplays',
        verbose_name=_('restaurant'),
    )
    restaurant_table = models.ForeignKey(
        'restaurants.RestaurantTable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gameplays',
        verbose_name=_('restaurant table'),
    )
    assigned_reward = models.ForeignKey(
        'coupons.Reward',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_gameplays',
        verbose_name=_('assigned reward'),
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='gameplays',
        verbose_name=_('game'),
    )
    score = models.PositiveIntegerField(_('score'), default=0)
    completed = models.BooleanField(_('completed'), default=False)
    result = models.CharField(max_length=16, choices=Result.choices, default=Result.ASSIGNED)
    play_date = models.DateField(default=timezone.localdate, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    challenge_data = models.JSONField(default=dict, blank=True)
    play_time = models.DurationField(_('play time'), null=True, blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    device = models.CharField(_('device'), max_length=255, blank=True)

    class Meta:
        verbose_name = _('gameplay')
        verbose_name_plural = _('gameplays')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['restaurant', 'game']),
            models.Index(fields=['customer', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'restaurant', 'play_date'],
                name='one_gameplay_per_customer_restaurant_day',
            ),
        ]

    def __str__(self):
        return f'{self.customer} — {self.game.name} @ {self.restaurant.restaurant_name}'
