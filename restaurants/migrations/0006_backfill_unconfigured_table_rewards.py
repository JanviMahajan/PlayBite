from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def assign_existing_all_game_rewards(apps, schema_editor):
    Restaurant = apps.get_model('restaurants', 'Restaurant')
    RestaurantTable = apps.get_model('restaurants', 'RestaurantTable')
    Reward = apps.get_model('coupons', 'Reward')
    today = timezone.localdate()
    database = schema_editor.connection.alias

    restaurants = Restaurant.objects.using(database).filter(
        branches__tables__reward__isnull=True,
    ).distinct()
    for restaurant in restaurants.iterator():
        reward = Reward.objects.using(database).filter(
            restaurant_id=restaurant.pk,
            is_active=True,
            game_eligibility='all',
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=today),
            Q(end_date__isnull=True) | Q(end_date__gte=today),
        ).order_by('-created_at', '-pk').first()
        if reward:
            RestaurantTable.objects.using(database).filter(
                branch__restaurant_id=restaurant.pk,
                reward__isnull=True,
            ).update(reward_id=reward.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('coupons', '0005_add_default_tap_reward'),
        ('restaurants', '0005_alter_restaurant_country'),
    ]

    operations = [
        migrations.RunPython(assign_existing_all_game_rewards, migrations.RunPython.noop),
    ]
