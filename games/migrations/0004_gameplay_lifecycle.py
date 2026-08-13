import datetime
import uuid

import django.utils.timezone
from django.db import migrations, models


def populate_lifecycle(apps, schema_editor):
    Gameplay = apps.get_model('games', 'Gameplay')
    used = set()
    for gameplay in Gameplay.objects.order_by('created_at', 'pk').iterator():
        gameplay.public_id = uuid.uuid4()
        day = (django.utils.timezone.localtime(gameplay.created_at).date()
               if gameplay.created_at else django.utils.timezone.localdate())
        key = (gameplay.customer_id, gameplay.restaurant_id, day)
        while key in used:
            day -= datetime.timedelta(days=1)
            key = (gameplay.customer_id, gameplay.restaurant_id, day)
        used.add(key)
        gameplay.play_date = day
        gameplay.result = 'won' if gameplay.completed else 'lost'
        gameplay.submitted_at = gameplay.updated_at or gameplay.created_at
        gameplay.completed_at = gameplay.updated_at if gameplay.completed else None
        gameplay.save(update_fields=['public_id', 'play_date', 'result', 'submitted_at', 'completed_at'])


class Migration(migrations.Migration):
    dependencies = [('games', '0003_normalize_mvp_games')]
    operations = [
        migrations.AddField('gameplay', 'public_id', models.UUIDField(null=True, editable=False)),
        migrations.AddField('gameplay', 'result', models.CharField(choices=[('assigned','Assigned'),('in_progress','In progress'),('won','Won'),('lost','Lost')], default='assigned', max_length=16)),
        migrations.AddField('gameplay', 'play_date', models.DateField(default=django.utils.timezone.localdate, db_index=True)),
        migrations.AddField('gameplay', 'started_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('gameplay', 'deadline', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('gameplay', 'completed_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('gameplay', 'submitted_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('gameplay', 'challenge_data', models.JSONField(blank=True, default=dict)),
        migrations.RunPython(populate_lifecycle, migrations.RunPython.noop),
        migrations.AlterField('gameplay', 'public_id', models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
        migrations.AddConstraint('gameplay', models.UniqueConstraint(fields=('customer','restaurant','play_date'), name='one_gameplay_per_customer_restaurant_day')),
    ]
