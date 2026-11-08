from django.db import migrations
import bcrypt


EMAIL = 'admin-linea@example.com'
PASSWORD = 'Cambiar123!'
LINE_NAME = 'San Benito'


def seed_admin_linea_user(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Line = apps.get_model('users', 'Line')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')
    Role = apps.get_model('roles', 'Role')

    line, _ = Line.objects.update_or_create(name=LINE_NAME, defaults={})
    role = Role.objects.filter(id='ADMIN_LINEA').first()
    if role is None:
        role = Role.objects.create(
            id='ADMIN_LINEA',
            name='Administrador de línea',
            image='https://cdn-icons-png.flaticon.com/512/3135/3135715.png',
            route='admin-linea/home',
        )

    hashed_password = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user, _ = User.objects.update_or_create(
        email=EMAIL,
        defaults={
            'name': 'Admin',
            'lastname': 'San Benito',
            'phone': '0000000000',
            'password': hashed_password,
            'line_id': line.id,
            'is_active': True,
        },
    )
    UserHasRoles.objects.get_or_create(id_user_id=user.id, id_rol_id=role.id)


def unseed_admin_linea_user(apps, schema_editor):
    User = apps.get_model('users', 'User')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')
    user = User.objects.filter(email=EMAIL).first()
    if user:
        UserHasRoles.objects.filter(id_user_id=user.id, id_rol_id='ADMIN_LINEA').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('roles', '0003_seed_admin_line_role'),
        ('users', '0002_line_and_user_admin_fields'),
    ]

    operations = [
        migrations.RunPython(seed_admin_linea_user, unseed_admin_linea_user),
    ]
