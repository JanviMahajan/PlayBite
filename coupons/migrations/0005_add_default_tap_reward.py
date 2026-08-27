from django.db import migrations


DESCRIPTION = 'Tap at exactly 10 seconds to win a free coffee.'


def add_default_rewards(apps, schema_editor):
    Restaurant = apps.get_model('restaurants', 'Restaurant')
    Game = apps.get_model('games', 'Game')
    Reward = apps.get_model('coupons', 'Reward')
    game = Game.objects.filter(slug='tap-at-ten').first()
    if game is None:
        return
    for restaurant in Restaurant.objects.iterator():
        reward, _ = Reward.objects.get_or_create(
            restaurant=restaurant,
            title='Free Coffee',
            game_eligibility='specific',
            description=DESCRIPTION,
            defaults={
                'reward_type': 'free_beverage',
                'coupon_valid_days': 7,
                'is_active': True,
            },
        )
        reward.eligible_games.add(game)


def remove_default_rewards(apps, schema_editor):
    apps.get_model('coupons', 'Reward').objects.filter(
        title='Free Coffee', description=DESCRIPTION, game_eligibility='specific',
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('coupons', '0004_repair_moonmuse_reward_dates'),
        ('games', '0006_add_tap_at_ten'),
    ]
    operations = [migrations.RunPython(add_default_rewards, remove_default_rewards)]
