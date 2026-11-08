from django.db import migrations
import bcrypt
from datetime import timedelta

LINE_NAME = 'San Benito'
ADMIN_EMAIL = 'admin-linea@example.com'
ADMIN_PASSWORD = 'Cambiar123!'
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


def restore_sanbenito_line(apps, schema_editor):
    from django.utils import timezone

    User = apps.get_model('users', 'User')
    Line = apps.get_model('users', 'Line')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')
    Role = apps.get_model('roles', 'Role')
    LineSubscription = apps.get_model('users', 'LineSubscription')

    line, _ = Line.objects.get_or_create(name=LINE_NAME, defaults={})

    admin_role = Role.objects.filter(id='ADMIN_LINEA').first()
    if admin_role:
        hashed = bcrypt.hashpw(
            ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        admin, _ = User.objects.update_or_create(
            email=ADMIN_EMAIL,
            defaults={
                'name': 'Admin',
                'lastname': 'San Benito',
                'phone': '0000000000',
                'password': hashed,
                'line_id': line.id,
                'is_active': True,
            },
        )
        UserHasRoles.objects.get_or_create(
            id_user_id=admin.id,
            id_rol_id=admin_role.id,
        )

    if not LineSubscription.objects.filter(line_id=line.id).exists():
        LineSubscription.objects.create(
            line_id=line.id,
            plan='piloto',
            status='activa',
            started_at=timezone.now(),
            pilot_ends_at=timezone.now() + timedelta(days=30),
        )

    User.objects.filter(email__in=DRIVER_EMAILS).update(line_id=line.id)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_reassign_sanbenito_drivers'),
        ('roles', '0004_seed_rabbit_super_role'),
    ]

    operations = [
        migrations.RunPython(restore_sanbenito_line, migrations.RunPython.noop),
    ]
