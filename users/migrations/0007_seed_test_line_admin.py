from datetime import timedelta

from django.db import migrations
import bcrypt

LINE_NAME = 'Linea Prueba'
EMAIL = 'admin-prueba@example.com'
PASSWORD = 'Cambiar123!'


def seed_test_line_admin(apps, schema_editor):
    from django.utils import timezone

    User = apps.get_model('users', 'User')
    Line = apps.get_model('users', 'Line')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')
    Role = apps.get_model('roles', 'Role')
    LineSubscription = apps.get_model('users', 'LineSubscription')

    line, _ = Line.objects.get_or_create(name=LINE_NAME, defaults={})

    admin_role = Role.objects.filter(id='ADMIN_LINEA').first()
    if admin_role is None:
        return

    hashed_password = bcrypt.hashpw(
        PASSWORD.encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')
    admin, _ = User.objects.update_or_create(
        email=EMAIL,
        defaults={
            'name': 'Admin',
            'lastname': 'Prueba',
            'phone': '0000000099',
            'password': hashed_password,
            'line_id': line.id,
            'is_active': True,
        },
    )
    UserHasRoles.objects.get_or_create(
        id_user_id=admin.id,
        id_rol_id=admin_role.id,
    )

    if not LineSubscription.objects.filter(line_id=line.id).exists():
        started = timezone.now()
        LineSubscription.objects.create(
            line_id=line.id,
            plan='piloto',
            status='activa',
            started_at=started,
            pilot_ends_at=started + timedelta(days=90),
            status_changed_at=started,
        )


def unseed_test_line_admin(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Line = apps.get_model('users', 'Line')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')

    user = User.objects.filter(email=EMAIL).first()
    if user:
        UserHasRoles.objects.filter(id_user_id=user.id, id_rol_id='ADMIN_LINEA').delete()
        user.delete()

    Line.objects.filter(name=LINE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_restore_seed_lines'),
        ('roles', '0003_seed_admin_line_role'),
    ]

    operations = [
        migrations.RunPython(seed_test_line_admin, unseed_test_line_admin),
    ]
