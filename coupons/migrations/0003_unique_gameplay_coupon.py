from django.db import migrations, models


def detach_duplicate_gameplay_coupons(apps, schema_editor):
    Coupon = apps.get_model('coupons', 'Coupon')
    seen = set()
    for coupon in Coupon.objects.exclude(gameplay_id=None).order_by('generated_at', 'pk').iterator():
        if coupon.gameplay_id in seen:
            coupon.gameplay_id = None
            coupon.save(update_fields=['gameplay'])
        else:
            seen.add(coupon.gameplay_id)


class Migration(migrations.Migration):
    dependencies = [('coupons', '0002_redemption_remove_reward_expiry_days_and_more'), ('games', '0004_gameplay_lifecycle')]
    operations = [
        migrations.RunPython(detach_duplicate_gameplay_coupons, migrations.RunPython.noop),
        migrations.AddConstraint(
            'coupon',
            models.UniqueConstraint(fields=('gameplay',), condition=models.Q(gameplay__isnull=False), name='one_coupon_per_gameplay'),
        ),
    ]
