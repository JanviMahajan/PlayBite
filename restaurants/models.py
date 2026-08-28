import uuid

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from playbite.models import TimeStampedModel


class Restaurant(TimeStampedModel):
    class Country(models.TextChoices):
        INDIA = 'IN', _('India')
        UAE = 'AE', _('United Arab Emirates')

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='restaurant',
        verbose_name=_('owner'),
    )
    restaurant_name = models.CharField(_('restaurant name'), max_length=255)
    logo = models.ImageField(_('logo'), upload_to='restaurant_logos/', null=True, blank=True)
    email = models.EmailField(_('email'), max_length=255, blank=True)
    phone = models.CharField(_('phone number'), max_length=32, blank=True)
    address = models.CharField(_('address'), max_length=512, blank=True)
    city = models.CharField(_('city'), max_length=128, blank=True)
    state = models.CharField(_('state'), max_length=128, blank=True)
    country = models.CharField(
        _('country'), max_length=2, choices=Country.choices, default=Country.INDIA,
    )
    pincode = models.CharField(_('pincode'), max_length=32, blank=True)
    description = models.TextField(_('description'), blank=True)
    opening_time = models.TimeField(_('opening time'), null=True, blank=True)
    closing_time = models.TimeField(_('closing time'), null=True, blank=True)
    primary_color = models.CharField(_('primary color'), max_length=7, default='#0d6efd')
    secondary_color = models.CharField(_('secondary color'), max_length=7, default='#6c757d')
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('restaurant')
        verbose_name_plural = _('restaurants')
        ordering = ['restaurant_name']

    def __str__(self):
        return self.restaurant_name

    def total_tables(self):
        return self.branches.aggregate(total=Count('tables'))['total'] or 0

    def total_coupons(self):
        from coupons.models import Coupon

        return Coupon.objects.filter(restaurant=self).count()

    def total_customers(self):
        from customer.models import Customer

        return Customer.objects.filter(gameplay__restaurant=self).distinct().count()


class Branch(TimeStampedModel):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name=_('restaurant'),
    )
    branch_name = models.CharField(_('branch name'), max_length=255)
    address = models.CharField(_('address'), max_length=512)
    city = models.CharField(_('city'), max_length=128)
    state = models.CharField(_('state'), max_length=128)
    country = models.CharField(_('country'), max_length=128)
    latitude = models.DecimalField(_('latitude'), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_('longitude'), max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(_('phone number'), max_length=32, blank=True)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('branch')
        verbose_name_plural = _('branches')
        unique_together = [['restaurant', 'branch_name']]
        ordering = ['restaurant', 'branch_name']

    def __str__(self):
        return f'{self.branch_name} — {self.restaurant.restaurant_name}'


class RestaurantTable(TimeStampedModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='tables',
        verbose_name=_('branch'),
    )
    table_number = models.CharField(_('table number'), max_length=32)
    qr_slug = models.UUIDField(_('QR slug'), default=uuid.uuid4, editable=False, unique=True)
    qr_image = models.ImageField(_('QR image'), upload_to='table_qr_codes/', null=True, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    class Meta:
        verbose_name = _('table')
        verbose_name_plural = _('tables')
        unique_together = [['branch', 'table_number']]
        ordering = ['branch', 'table_number']
        indexes = [
            models.Index(fields=['qr_slug']),
            models.Index(fields=['table_number']),
        ]

    def __str__(self):
        return f'Table {self.table_number} @ {self.branch.branch_name}'

    def get_qr_url(self):
        # Returns the play URL for this table's qr
        from django.urls import reverse
        return reverse('play', args=[str(self.qr_slug)])

    def generate_qr_slug(self, save=True):
        """Ensure the table has a qr_slug set and return it."""
        if not self.qr_slug:
            self.qr_slug = uuid.uuid4()
            if save:
                self.save(update_fields=['qr_slug'])
        return str(self.qr_slug)

    def generate_qr_image(self, site_url=None, save=True):
        """Generate a QR PNG embedding the play URL and store into qr_image field.
        Requires 'qrcode' and Pillow. If site_url is provided it will be used as absolute base.
        """
        try:
            import qrcode
            from io import BytesIO
            from django.core.files.base import ContentFile
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            # If libraries missing, do nothing silently (developer should install qrcode and pillow)
            return None

        # Build URL. PUBLIC_BASE_URL is opt-in for temporary tunnel/demo sessions.
        site_url = site_url or getattr(settings, 'PUBLIC_BASE_URL', '')
        slug = self.generate_qr_slug(save=save)
        if site_url:
            play_url = f"{site_url.rstrip('/')}/play/{slug}/"
        else:
            # Use relative URL
            play_url = f"/play/{slug}/"

        # Generate QR
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
        qr.add_data(play_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#111111", back_color="white").convert('RGB')

        # Compose final image with logo and branding
        width = 1200
        canvas = Image.new('RGB', (width, width + 260), 'white')
        draw = ImageDraw.Draw(canvas)

        # Paste QR centered
        qr_size = min(width - 200, qr_img.size[0])
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
        qr_x = (width - qr_size) // 2
        qr_y = 120
        canvas.paste(qr_img, (qr_x, qr_y))

        # Restaurant logo (if available)
        try:
            if self.branch and self.branch.restaurant and self.branch.restaurant.logo:
                logo_path = self.branch.restaurant.logo.path
                logo = Image.open(logo_path).convert('RGBA')
                logo.thumbnail((160, 160), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
                logo_x = (width - logo.size[0]) // 2
                logo_y = 20
                canvas.paste(logo, (logo_x, logo_y), logo)
        except Exception:
            pass

        # Small PlayBite text below QR
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        text = "Scan to Play & Win Rewards"
        if hasattr(draw, 'textbbox'):
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = right - left, bottom - top
        else:
            text_w, text_h = draw.textsize(text, font=font)
        draw.text(((width - text_w) / 2, qr_y + qr_size + 20), text, fill=(45, 45, 45), font=font)

        # Save to in-memory file
        bio = BytesIO()
        canvas.save(bio, format='PNG', optimize=True)
        bio.seek(0)

        filename = f'table-{self.pk or "new"}-qr.png'
        if save:
            self.qr_image.save(filename, ContentFile(bio.read()), save=False)
            self.save(update_fields=['qr_image'])
        else:
            return ContentFile(bio.read(), name=filename)

        return self.qr_image


class QRScan(TimeStampedModel):
    table = models.ForeignKey(RestaurantTable, on_delete=models.CASCADE, related_name='scans')
    scanned_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device = models.CharField(max_length=128, blank=True)
    browser = models.CharField(max_length=128, blank=True)
    os = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ['-scanned_at']

    def __str__(self):
        return f'QR scan @ {self.scanned_at} - {self.table}'
