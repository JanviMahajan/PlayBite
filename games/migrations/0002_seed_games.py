from django.db import migrations
from datetime import timedelta


def create_default_games(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    games = [
        {
            'name': 'Memory Match',
            'slug': 'memory-match',
            'description': 'Test guest memory and speed with a matching tile game.',
            'difficulty': 'easy',
            'duration': '00:02:00',
            'is_active': True,
        },
        {
            'name': 'Maze Escape',
            'slug': 'maze-escape',
            'description': 'Navigate a short maze before time runs out.',
            'difficulty': 'medium',
            'duration': '00:03:30',
            'is_active': True,
        },
        {
            'name': 'Fruit Slice Challenge',
            'slug': 'fruit-slice-challenge',
            'description': 'Slice the falling fruit as quickly as possible.',
            'difficulty': 'hard',
            'duration': '00:02:30',
            'is_active': True,
        },
    ]

    for game_data in games:
        # Ensure duration is a timedelta for DurationField
        dur = game_data.get('duration')
        if isinstance(dur, str):
            try:
                h, m, s = [int(x) for x in dur.split(':')]
                game_data['duration'] = timedelta(hours=h, minutes=m, seconds=s)
            except Exception:
                game_data['duration'] = timedelta(seconds=0)
        Game.objects.update_or_create(slug=game_data['slug'], defaults=game_data)


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_games),
    ]
