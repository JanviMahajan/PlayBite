from django.utils import timezone

from restaurants.models import RestaurantTable


def assign_reward_to_unconfigured_tables(reward):
    """Attach an available all-games reward without replacing table choices."""
    if not reward.is_currently_valid() or reward.game_eligibility != reward.GameEligibility.ALL:
        return 0
    return RestaurantTable.objects.filter(
        branch__restaurant=reward.restaurant,
        reward__isnull=True,
    ).update(reward=reward, updated_at=timezone.now())
