from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from coupons.models import Coupon
from coupons.services.redeemer import validate_qr_token


def coupon_from_private_token(token):
    """Resolve one coupon only after validating its signed, stored token."""
    payload = validate_qr_token(token)
    coupon_code = payload.get('coupon_code') if payload else None
    if not coupon_code:
        raise Http404('Coupon not found.')
    try:
        return Coupon.objects.select_related('restaurant', 'reward').get(
            coupon_code=coupon_code,
            qr_token=token,
        )
    except Coupon.DoesNotExist as exc:
        raise Http404('Coupon not found.') from exc


def coupon_customer_status(coupon, now=None):
    """Return the customer-facing status without changing redemption state."""
    now = now or timezone.now()
    if coupon.status == Coupon.Status.REDEEMED:
        return 'redeemed', _('Already Redeemed')
    if coupon.status == Coupon.Status.EXPIRED or (coupon.expiry_at and now > coupon.expiry_at):
        return 'expired', _('Expired')
    if not coupon.valid_from or now < coupon.valid_from:
        return 'pending', _('Available Tomorrow')
    if coupon.expiry_at and now <= coupon.expiry_at:
        return 'active', _('Ready to Use')
    return 'expired', _('Expired')


def public_coupon_url(request, coupon):
    path = reverse('coupon_public:view', kwargs={'token': coupon.qr_token})
    base_url = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
    return f'{base_url}{path}' if base_url else request.build_absolute_uri(path)


def whatsapp_share_url(request, coupon):
    view_url = public_coupon_url(request, coupon)
    valid_from = timezone.localtime(coupon.valid_from).strftime('%d %b %Y') if coupon.valid_from else '—'
    expiry = timezone.localtime(coupon.expiry_at).strftime('%d %b %Y') if coupon.expiry_at else '—'
    message = '\n'.join([
        _('🎉 I won a PlayBite treat!'), '',
        f'🍔 {coupon.reward.title}',
        f'📍 {coupon.restaurant.restaurant_name}', '',
        _('🎟 Coupon: %(code)s') % {'code': coupon.coupon_code},
        _('📅 Valid from: %(date)s') % {'date': valid_from},
        _('⏳ Expires: %(date)s') % {'date': expiry}, '',
        _('View my coupon:'), view_url, '',
        _("I'll be back for my treat! ✨"),
    ])
    return f'https://wa.me/?{urlencode({"text": message})}'
