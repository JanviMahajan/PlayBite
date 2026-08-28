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


def _ensure_existing_coupon_is_deliverable(coupon, gameplay):
    """Repair an idempotently reused coupon that predates delivery fields."""
    update_fields = []
    if not coupon.valid_from or not coupon.expiry_at:
        coupon.set_validity_windows(gameplay.play_date)
        update_fields.extend(['valid_from', 'expiry_at'])
    if not coupon.qr_token:
        coupon.qr_token = signing.dumps({
            'coupon_code': coupon.coupon_code,
            'nonce': secrets.token_urlsafe(16),
        })
        update_fields.append('qr_token')
    if update_fields:
        update_fields.append('updated_at')
        coupon.save(update_fields=update_fields)
    return coupon


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


def _replacement_reward_for_table(gameplay, table, exclude_id=None):
    candidates = eligible_rewards_for_gameplay(gameplay).filter(
        applicable_tables=table,
    ).distinct()
    if exclude_id:
        candidates = candidates.exclude(pk=exclude_id)
    available = [
        reward for reward in candidates
        if reward_redemption_limits_allow_coupon(reward, gameplay.play_date)
    ]
    return secrets.choice(available) if available else None


@transaction.atomic
def generate_coupon_for_gameplay(gameplay):
    """Create one coupon from the exact reward assigned to the scanned table."""
    from games.models import Gameplay
    # Lock only the non-null Gameplay row. PostgreSQL rejects FOR UPDATE when
    # the same query outer-joins nullable relationships such as assigned_reward.
    gameplay = Gameplay.objects.select_for_update().select_related(
        'restaurant', 'game', 'customer'
    ).get(pk=gameplay.pk)
    existing = Coupon.objects.filter(gameplay=gameplay).first()
    if existing:
        coupon = _ensure_existing_coupon_is_deliverable(existing, gameplay)
        logger.info(
            'COUPON FLOW reused gameplay=%s game=%s restaurant=%s table=%s reward=%s coupon=%s code=%s redirect_ready=%s',
            gameplay.pk, gameplay.game_id, gameplay.restaurant_id,
            gameplay.restaurant_table_id, coupon.reward_id, coupon.pk,
            coupon.coupon_code, bool(coupon.qr_token),
        )
        return coupon
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
        # The owner may configure a reward after today's gameplay was assigned.
        # Recover server-side so the consumed daily attempt can still earn it.
        replacement = _replacement_reward_for_table(gameplay, table)
        if not replacement:
            logger.warning('No reward is configured for table %s (gameplay %s)', table.pk, gameplay.pk)
            return None
        gameplay.assigned_reward = replacement
        gameplay.save(update_fields=['assigned_reward', 'updated_at'])
    reward = gameplay.assigned_reward
    if reward.restaurant_id != gameplay.restaurant_id:
        logger.error(
            'Gameplay %s reward %s belongs to restaurant %s, not gameplay restaurant %s',
            gameplay.pk, reward.pk, reward.restaurant_id, gameplay.restaurant_id,
        )
        return None
    reward_is_applicable = reward.applicable_tables.filter(pk=table.pk).exists()
    reward_is_eligible = eligible_rewards_for_gameplay(gameplay).filter(pk=reward.pk).exists()
    reward_limit_available = reward_redemption_limits_allow_coupon(reward, gameplay.play_date)
    if not (reward_is_applicable and reward_is_eligible and reward_limit_available):
        logger.warning(
            'Assigned reward %s is stale for gameplay %s (applicable=%s eligible=%s limit_available=%s)',
            reward.pk, gameplay.pk, reward_is_applicable, reward_is_eligible,
            reward_limit_available,
        )
        replacement = _replacement_reward_for_table(gameplay, table, exclude_id=reward.pk)
        if not replacement:
            return None
        reward = replacement
        gameplay.assigned_reward = reward
        gameplay.save(update_fields=['assigned_reward', 'updated_at'])

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

    logger.info(
        'COUPON FLOW created gameplay=%s game=%s restaurant=%s branch=%s table=%s result=%s reward=%s active=%s eligible=%s coupon=%s code=%s redirect_ready=%s',
        gameplay.pk, gameplay.game_id, gameplay.restaurant_id, table.branch_id,
        table.pk, gameplay.result, reward.pk, reward.is_active, True, coupon.pk,
        coupon.coupon_code, bool(coupon.qr_token),
    )

    return coupon
