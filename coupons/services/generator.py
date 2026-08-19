import secrets
import logging

from django.db import transaction
from django.db.models import Q
from django.core import signing
from django.utils import timezone

from coupons.models import Coupon, Reward

import uuid


logger = logging.getLogger(__name__)


def _unique_code(prefix='PB', length=6):
    import random, string
    while True:
        s = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        code = f'{prefix}-{s}'
        if not Coupon.objects.filter(coupon_code=code).exists():
            return code


def eligible_rewards_for_gameplay(gameplay, at_date=None):
    """Return rewards available to win for this gameplay's restaurant."""
    at_date = at_date or gameplay.play_date or timezone.localdate()
    return Reward.objects.filter(
        restaurant_id=gameplay.restaurant_id,
        is_active=True,
    ).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=at_date),
        Q(end_date__isnull=True) | Q(end_date__gte=at_date),
    )


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
    if (gameplay.restaurant_table_id
            and gameplay.restaurant_table.branch.restaurant_id != gameplay.restaurant_id):
        logger.error(
            'Gameplay %s restaurant %s does not match table restaurant %s',
            gameplay.pk,
            gameplay.restaurant_id,
            gameplay.restaurant_table.branch.restaurant_id,
        )
        return None

    rewards = eligible_rewards_for_gameplay(gameplay)
    best = rewards.order_by('-created_at', '-pk').first()
    if best is None:
        logger.warning(
            'No eligible reward for gameplay %s restaurant %s; active=%s eligible=%s play_date=%s',
            gameplay.pk,
            gameplay.restaurant_id,
            Reward.objects.filter(restaurant_id=gameplay.restaurant_id, is_active=True).count(),
            rewards.count(),
            gameplay.play_date,
        )
        return None

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
    payload = {'coupon_code': coupon.coupon_code, 'nonce': secrets.token_urlsafe(16)}
    token = signing.dumps(payload)
    coupon.qr_token = token
    coupon.save(update_fields=['valid_from', 'expiry_at', 'qr_token', 'updated_at'])

    return coupon
