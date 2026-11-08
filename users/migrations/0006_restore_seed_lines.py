from django.db import migrations
import bcrypt

ADMIN_EMAIL = 'admin-linea@example.com'
ADMIN_PASSWORD = 'Cambiar123!'
LINE_NAME = 'San Benito'
SUPER_EMAIL = 'super-admin@example.com'
SUPER_PASSWORD = 'Cambiar123!'


def restore_seed_lines(apps, schema_editor):
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

    super_role = Role.objects.filter(id='RABBIT_SUPER').first()
    if super_role:
        hashed = bcrypt.hashpw(
            SUPER_PASSWORD.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        super_user, _ = User.objects.update_or_create(
            email=SUPER_EMAIL,
            defaults={
                'name': 'Super',
                'lastname': 'Rabbit',
                'phone': '0000000001',
                'password': hashed,
                'is_active': True,
            },
        )
        UserHasRoles.objects.get_or_create(
            id_user_id=super_user.id,
            id_rol_id=super_role.id,
        )

    if not LineSubscription.objects.filter(line_id=line.id).exists():
        from django.utils import timezone

        LineSubscription.objects.create(
            line_id=line.id,
            plan='piloto',
            status='activa',
            started_at=timezone.now(),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_seed_rabbit_super_user'),
        ('roles', '0004_seed_rabbit_super_role'),
    ]

    operations = [
        migrations.RunPython(restore_seed_lines, migrations.RunPython.noop),
    ]
