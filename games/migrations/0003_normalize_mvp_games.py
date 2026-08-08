from datetime import timedelta

from django.db import migrations


def normalize_mvp_games(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    Game.objects.filter(slug='fruit-slice-challenge').update(slug='fruit-slice')
    Game.objects.filter(
        slug__in=['memory-match', 'maze-escape', 'fruit-slice']
    ).update(duration=timedelta(seconds=45))


class Migration(migrations.Migration):
    dependencies = [('games', '0002_seed_games')]
    operations = [migrations.RunPython(normalize_mvp_games, migrations.RunPython.noop)]
