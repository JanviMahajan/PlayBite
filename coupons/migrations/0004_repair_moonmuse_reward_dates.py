from django.db import migrations


def repair_moonmuse_reward_dates(apps, schema_editor):
    """Clear inaccessible legacy dates on the affected production reward."""
    Reward = apps.get_model('coupons', 'Reward')
    Reward.objects.filter(
        restaurant__restaurant_name__iexact='moonmuse',
        title__iexact='20% discount on order above inr100',
        is_active=True,
    ).update(start_date=None, end_date=None)


class Migration(migrations.Migration):
    dependencies = [
        ('coupons', '0003_unique_gameplay_coupon'),
    ]

    operations = [
        migrations.RunPython(repair_moonmuse_reward_dates, migrations.RunPython.noop),
    ]
