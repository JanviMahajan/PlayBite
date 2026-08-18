from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
from django.core import signing

from coupons.models import Coupon, Reward

import uuid


def _unique_code(prefix='PB', length=6):
    import random, string
    while True:
        s = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        code = f'{prefix}-{s}'
        if not Coupon.objects.filter(coupon_code=code).exists():
            return code


@transaction.atomic
def generate_coupon_for_gameplay(gameplay):
    """Determine eligible rewards for the gameplay, pick the highest value one, create Coupon.
    Returns coupon instance or None if none available.
    """
    from games.models import Gameplay
    gameplay = Gameplay.objects.select_for_update().select_related(
        'restaurant', 'game', 'customer', 'restaurant_table__branch'
    ).get(pk=gameplay.pk)
    existing = Coupon.objects.filter(gameplay=gameplay).first()
    if existing:
        return existing
    if gameplay.result != Gameplay.Result.WON or not gameplay.completed:
        return None
    restaurant = gameplay.restaurant
    game = gameplay.game

    # collect candidate rewards
    rewards = Reward.objects.filter(restaurant=restaurant, is_active=True)
    valid_candidates = []
    today = gameplay.play_date
    for r in rewards:
        # game eligibility
        if r.game_eligibility == Reward.GameEligibility.SPECIFIC:
            if not r.eligible_games.filter(pk=game.pk).exists():
                continue
        # redemption limits
        # total
        total_count = r.coupons.count()
        if r.max_total_redemptions and total_count >= r.max_total_redemptions:
            continue
        # daily
        if r.max_daily_redemptions:
            day_start = timezone.datetime.combine(today, timezone.datetime.min.time())
            day_start = timezone.make_aware(day_start, timezone.get_current_timezone())
            day_end = day_start + timezone.timedelta(days=1)
            day_count = r.coupons.filter(generated_at__gte=day_start, generated_at__lt=day_end).count()
            if day_count >= r.max_daily_redemptions:
                continue
        valid_candidates.append(r)

    if not valid_candidates:
        return None

    # Reward value is not part of the customer flow; use the first eligible
    # configured reward deterministically.
    best = valid_candidates[0]

    # create coupon
    coupon_code = _unique_code('PB', 6)
    # create coupon with pending status and set validity windows
    coupon = Coupon.objects.create(
        customer=gameplay.customer,
        restaurant=restaurant,
        branch=gameplay.restaurant_table.branch if gameplay.restaurant_table else None,
        table=gameplay.restaurant_table,
        reward=best,
        gameplay=gameplay,
        coupon_code=coupon_code,
        status=Coupon.Status.PENDING,
    )
    coupon.set_validity_windows(gameplay.play_date)
    # The signed token is essential; generating a stored QR image is optional.
    payload = {'coupon_code': coupon.coupon_code, 'ts': timezone.now().isoformat()}
    token = signing.dumps(payload)
    coupon.qr_token = token
    # Generate the legacy stored QR image when storage is available. Customer
    # coupon pages generate their QR from qr_token and do not depend on this file.
    try:
        import qrcode
        from io import BytesIO
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
        qr.add_data(token)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#111111", back_color="white").convert('RGB')
        bio = BytesIO(); img.save(bio, format='PNG'); bio.seek(0)
        coupon.qr_image.save(f'coupon-{coupon.coupon_code}.png', ContentFile(bio.read()), save=False)
    except Exception:
        pass

    coupon.save()

    return coupon
