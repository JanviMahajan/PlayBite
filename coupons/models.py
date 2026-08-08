import uuid
from datetime import timedelta, datetime, time as dtime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core import signing

from playbite.models import TimeStampedModel


class Reward(TimeStampedModel):
    class RewardType(models.TextChoices):
        PERCENTAGE = 'percentage', _('Percentage Discount')
        FLAT = 'flat', _('Flat Discount')
        FREE_ITEM = 'free_item', _('Free Item')
        BUY_ONE_GET_ONE = 'bogo', _('Buy One Get One')
        FREE_BEVERAGE = 'free_beverage', _('Free Beverage')
        FREE_DESSERT = 'free_dessert', _('Free Dessert')
        CUSTOM = 'custom', _('Custom Reward')

    class GameEligibility(models.TextChoices):
        ALL = 'all', _('All Games')
        SPECIFIC = 'specific', _('Specific Games')

    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='rewards',
        verbose_name=_('restaurant'),
    )
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    reward_type = models.CharField(
        _('reward type'),
        max_length=32,
        choices=RewardType.choices,
        default=RewardType.PERCENTAGE,
    )
    reward_value = models.DecimalField(_('reward value'), max_digits=10, decimal_places=2, default=0)
    minimum_score = models.PositiveIntegerField(_('minimum score'), default=0)

    game_eligibility = models.CharField(_('game eligibility'), max_length=16, choices=GameEligibility.choices, default=GameEligibility.ALL)
    eligible_games = models.ManyToManyField('games.Game', blank=True, related_name='eligible_rewards')

    start_date = models.DateField(_('start date'), null=True, blank=True)
    end_date = models.DateField(_('end date'), null=True, blank=True)

    coupon_valid_days = models.PositiveSmallIntegerField(_('coupon valid days'), default=7)

    max_daily_redemptions = models.PositiveIntegerField(_('max daily redemptions'), null=True, blank=True)
    max_total_redemptions = models.PositiveIntegerField(_('max total redemptions'), null=True, blank=True)

    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('reward')
        verbose_name_plural = _('rewards')
        ordering = ['restaurant', 'title']
        indexes = [models.Index(fields=['restaurant', 'reward_type'])]

    def __str__(self):
        return f'{self.title} — {self.restaurant.restaurant_name}'

    def is_currently_valid(self):
        today = timezone.localdate()
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return self.is_active

    def value_score(self):
        """Return a numeric score useful to pick highest-value reward.
        Percentage and flat use reward_value; free items use a high constant.
        """
        if self.reward_type == self.RewardType.PERCENTAGE or self.reward_type == self.RewardType.FLAT:
            try:
                return float(self.reward_value)
            except Exception:
                return 0.0
        # give priority to free items
        if self.reward_type in {self.RewardType.FREE_ITEM, self.RewardType.FREE_BEVERAGE, self.RewardType.FREE_DESSERT}:
            return 100000.0
        if self.reward_type == self.RewardType.BUY_ONE_GET_ONE:
            return 50000.0
        return 0.0


def _generate_coupon_code():
    # PB-XXXXXX (6 chars alnum)
    token = uuid.uuid4().hex.upper()[:8]
    return f'PB-{token}'


class Coupon(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ACTIVE = 'active', _('Active')
        EXPIRED = 'expired', _('Expired')
        REDEEMED = 'redeemed', _('Redeemed')

    customer = models.ForeignKey(
        'customer.Customer',
        on_delete=models.CASCADE,
        related_name='coupons',
        verbose_name=_('customer'),
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='coupons',
        verbose_name=_('restaurant'),
    )
    branch = models.ForeignKey(
        'restaurants.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupons',
        verbose_name=_('branch'),
    )
    table = models.ForeignKey(
        'restaurants.RestaurantTable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupons',
        verbose_name=_('table'),
    )
    reward = models.ForeignKey(
        Reward,
        on_delete=models.CASCADE,
        related_name='coupons',
        verbose_name=_('reward'),
    )
    gameplay = models.ForeignKey(
        'games.Gameplay',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupons',
        verbose_name=_('gameplay'),
    )

    coupon_code = models.CharField(
        _('coupon code'),
        max_length=32,
        unique=True,
        default=_generate_coupon_code,
        editable=False,
    )

    status = models.CharField(_('status'), max_length=16, choices=Status.choices, default=Status.PENDING)
    generated_at = models.DateTimeField(_('generated at'), auto_now_add=True)

    valid_from = models.DateTimeField(_('valid from'), null=True, blank=True)
    expiry_at = models.DateTimeField(_('expiry at'), null=True, blank=True)

    qr_token = models.CharField(_('qr token'), max_length=255, null=True, blank=True, editable=False)
    qr_image = models.ImageField(_('QR image'), upload_to='coupon_qr_codes/', null=True, blank=True)

    redemption_count = models.PositiveIntegerField(_('redemption count'), default=0)

    class Meta:
        verbose_name = _('coupon')
        verbose_name_plural = _('coupons')
        ordering = ['-generated_at']
        indexes = [models.Index(fields=['coupon_code', 'generated_at']), models.Index(fields=['status'])]

    def __str__(self):
        return f'{self.coupon_code} — {self.reward.title}'

    def set_validity_windows(self):
        """Set valid_from to the next calendar day's 00:00 (server local) and expiry accordingly."""
        today = timezone.localdate()
        next_day = today + timedelta(days=1)
        # midnight next day
        vf = datetime.combine(next_day, dtime.min)
        vf = timezone.make_aware(vf, timezone.get_current_timezone())
        self.valid_from = vf
        self.expiry_at = vf + timedelta(days=int(self.reward.coupon_valid_days or 7))

    def generate_qr(self, save=True):
        """Generate a signed token for the coupon and an image if qrcode/Pillow present."""
        payload = {'code': self.coupon_code, 'generated': timezone.now().isoformat()}
        token = signing.dumps(payload)
        self.qr_token = token

        # create QR image
        try:
            import qrcode
            from PIL import Image
            from io import BytesIO
            from django.core.files.base import ContentFile
        except Exception:
            return None

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
        # point to a secure redemption endpoint (placeholder)
        redemption_url = f"/coupon/redeem/{token}/"
        qr.add_data(redemption_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#111111", back_color="white").convert('RGB')

        bio = BytesIO()
        img.save(bio, format='PNG')
        bio.seek(0)
        filename = f'coupon-{self.coupon_code}.png'
        if save:
            self.qr_image.save(filename, ContentFile(bio.read()), save=False)
            self.save(update_fields=['qr_image', 'qr_token'])
        else:
            return ContentFile(bio.read(), name=filename)

        return self.qr_image

    def mark_active_if_needed(self):
        """Activate coupon if valid_from has passed."""
        if self.status == self.Status.PENDING and self.valid_from and timezone.now() >= self.valid_from:
            self.status = self.Status.ACTIVE
            self.save(update_fields=['status'])

    def is_active_now(self):
        return self.status == self.Status.ACTIVE and self.valid_from and self.expiry_at and (self.valid_from <= timezone.now() <= self.expiry_at)


class Redemption(TimeStampedModel):
    coupon = models.OneToOneField('Coupon', on_delete=models.CASCADE, related_name='redemption')
    redeemed_at = models.DateTimeField(_('redeemed at'), null=True, blank=True)
    redeemed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='redemptions')
    branch = models.ForeignKey('restaurants.Branch', on_delete=models.SET_NULL, null=True, blank=True)
    device = models.CharField(_('device'), max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    reason = models.TextField(_('reason'), blank=True)

    def mark_redeemed(self, user=None, branch=None, device=None, ip=None):
        self.redeemed_at = timezone.now()
        if user:
            self.redeemed_by = user
        if branch:
            self.branch = branch
        if device:
            self.device = device[:255]
        if ip:
            self.ip_address = ip
        self.save()

    class Meta:
        verbose_name = _('redemption')
        verbose_name_plural = _('redemptions')
        ordering = ['-redeemed_at']
