from datetime import timedelta

from django.db import migrations


def add_tap_at_ten(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    Game.objects.update_or_create(
        slug='tap-at-ten',
        defaults={
            'name': 'Tap at 10 Seconds',
            'description': 'Tap as close to exactly 10 seconds as possible!',
            'duration': timedelta(seconds=15),
            'difficulty': 'medium',
            'is_active': True,
        },
    )


def remove_tap_at_ten(apps, schema_editor):
    apps.get_model('games', 'Game').objects.filter(slug='tap-at-ten').update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [('games', '0005_seed_objective_games')]
    operations = [migrations.RunPython(add_tap_at_ten, remove_tap_at_ten)]
