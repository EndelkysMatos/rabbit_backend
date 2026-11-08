from datetime import timedelta

from django.db import migrations


def align_pilot_one_month(apps, schema_editor):
    LineSubscription = apps.get_model('users', 'LineSubscription')

    for sub in LineSubscription.objects.filter(plan='piloto'):
        if not sub.started_at:
            continue
        expected_end = sub.started_at + timedelta(days=30)
        if sub.pilot_ends_at is None or sub.pilot_ends_at > expected_end:
            sub.pilot_ends_at = expected_end
            sub.save(update_fields=['pilot_ends_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_restore_sanbenito_line'),
    ]

    operations = [
        migrations.RunPython(align_pilot_one_month, migrations.RunPython.noop),
    ]
