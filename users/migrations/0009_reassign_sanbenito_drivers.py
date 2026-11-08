from django.db import migrations

LINE_NAME = 'San Benito'
DRIVER_EMAILS = [
    'driver1@example.com',
    'driver2@example.com',
    'driver3@example.com',
    'driver4@example.com',
    'driver5@example.com',
    'driver6@example.com',
    'driver7@example.com',
    'driver8@example.com',
]


def reassign_sanbenito_drivers(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Line = apps.get_model('users', 'Line')

    line = Line.objects.filter(name=LINE_NAME).first()
    if not line:
        return

    User.objects.filter(
        email__in=DRIVER_EMAILS,
        line_id__isnull=True,
    ).update(line_id=line.id)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_reseed_test_line_admin'),
    ]

    operations = [
        migrations.RunPython(reassign_sanbenito_drivers, migrations.RunPython.noop),
    ]
