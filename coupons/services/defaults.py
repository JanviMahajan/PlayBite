DEFAULT_COFFEE_DESCRIPTION = 'Tap at exactly 10 seconds to win a free coffee.'


def ensure_default_tap_reward(restaurant):
    """Ensure newly-created restaurants receive the platform default reward."""
    from coupons.models import Reward
    from games.models import Game

    game = Game.objects.filter(slug='tap-at-ten', is_active=True).first()
    if game is None:
        return None
    reward, _ = Reward.objects.get_or_create(
        restaurant=restaurant,
        title='Free Coffee',
        game_eligibility=Reward.GameEligibility.SPECIFIC,
        description=DEFAULT_COFFEE_DESCRIPTION,
        defaults={
            'reward_type': Reward.RewardType.FREE_BEVERAGE,
            'coupon_valid_days': 7,
            'is_active': True,
        },
    )
    reward.eligible_games.add(game)
    return reward
