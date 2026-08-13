from datetime import timedelta
from django.db import migrations


def seed_games(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    games = [
        ('burger-stack', 'Burger Stack', 'Build the perfect burger before time runs out!', 25),
        ('order-rush', 'Order Rush', "Memorize the customer's order and serve it in time!", 20),
        ('memory-match', 'Memory Match', 'Find all the matching café treats before time runs out!', 30),
        ('pizza-slice', 'Pizza Slice Timing', 'Time each tap to make three perfect pizza cuts!', 20),
    ]
    active = []
    for slug, name, description, seconds in games:
        Game.objects.update_or_create(slug=slug, defaults={
            'name': name, 'description': description, 'duration': timedelta(seconds=seconds),
            'difficulty': 'medium', 'is_active': True,
        })
        active.append(slug)
    Game.objects.exclude(slug__in=active).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [('games', '0004_gameplay_lifecycle')]
    operations = [migrations.RunPython(seed_games, migrations.RunPython.noop)]
