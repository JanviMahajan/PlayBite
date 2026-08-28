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


def eligible_rewards_for_restaurant(restaurant, at_date=None):
    """Return the single source of truth for currently available rewards."""
    at_date = at_date or timezone.localdate()
    return Reward.objects.filter(
        restaurant=restaurant,
        is_active=True,
    ).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=at_date),
        Q(end_date__isnull=True) | Q(end_date__gte=at_date),
    )


def eligible_rewards_for_gameplay(gameplay, at_date=None):
    rewards = eligible_rewards_for_restaurant(
        gameplay.restaurant_id,
        at_date=at_date or gameplay.play_date,
    )
    return rewards.filter(
        Q(game_eligibility=Reward.GameEligibility.ALL)
        | Q(game_eligibility=Reward.GameEligibility.SPECIFIC, eligible_games=gameplay.game)
    ).distinct()


def reward_redemption_limits_allow_coupon(reward, at_date=None):
    """Honor existing reward redemption caps before issuing another coupon."""
    from coupons.models import Redemption

    redemptions = Redemption.objects.filter(
        coupon__reward=reward,
        redeemed_at__isnull=False,
    )
    if reward.max_total_redemptions is not None:
        if redemptions.count() >= reward.max_total_redemptions:
            return False
    if reward.max_daily_redemptions is not None:
        at_date = at_date or timezone.localdate()
        if redemptions.filter(redeemed_at__date=at_date).count() >= reward.max_daily_redemptions:
            return False
    return True


@transaction.atomic
def generate_coupon_for_gameplay(gameplay):
    """Create one coupon from the exact reward assigned to the scanned table."""
    from games.models import Gameplay
    # Lock only the non-null Gameplay row. PostgreSQL rejects FOR UPDATE when
    # the same query outer-joins the nullable restaurant_table relationship.
    gameplay = Gameplay.objects.select_for_update().select_related(
        'restaurant', 'game', 'customer', 'assigned_reward'
    ).get(pk=gameplay.pk)
    existing = Coupon.objects.filter(gameplay=gameplay).first()
    if existing:
        return existing
    if gameplay.result != Gameplay.Result.WON or not gameplay.completed:
        return None
    restaurant = gameplay.restaurant
    if not gameplay.restaurant_table_id:
        logger.warning('No table is associated with gameplay %s', gameplay.pk)
        return None
    from restaurants.models import RestaurantTable
    table = RestaurantTable.objects.select_for_update().select_related('branch').get(
        pk=gameplay.restaurant_table_id
    )
    if table.branch.restaurant_id != gameplay.restaurant_id:
        logger.error(
            'Gameplay %s restaurant %s does not match table restaurant %s',
            gameplay.pk,
            gameplay.restaurant_id,
            table.branch.restaurant_id,
        )
        return None
    if not gameplay.assigned_reward_id:
        logger.warning('No reward is configured for table %s (gameplay %s)', table.pk, gameplay.pk)
        return None
    reward = gameplay.assigned_reward
    if reward.restaurant_id != gameplay.restaurant_id:
        logger.error(
            'Gameplay %s reward %s belongs to restaurant %s, not gameplay restaurant %s',
            gameplay.pk, reward.pk, reward.restaurant_id, gameplay.restaurant_id,
        )
        return None
    if not reward.applicable_tables.filter(pk=table.pk).exists():
        logger.error('Gameplay reward %s does not apply to table %s', reward.pk, table.pk)
        return None
    reward = eligible_rewards_for_gameplay(gameplay).filter(pk=reward.pk).first()
    if reward is None:
        logger.warning(
            'Assigned reward %s is not eligible for gameplay %s on %s',
            gameplay.assigned_reward_id, gameplay.pk, gameplay.play_date,
        )
        return None
    if not reward_redemption_limits_allow_coupon(reward, gameplay.play_date):
        logger.warning('Assigned reward %s has reached a configured redemption limit', reward.pk)
        return None

    # create coupon
    coupon_code = _unique_code('PB', 6)
    # create coupon with pending status and set validity windows
    coupon = Coupon.objects.create(
        customer=gameplay.customer,
        restaurant=restaurant,
        branch=table.branch if table else None,
        table=table,
        reward=reward,
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
