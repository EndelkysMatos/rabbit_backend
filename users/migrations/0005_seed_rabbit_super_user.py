from django.db import migrations
import bcrypt

EMAIL = 'super-admin@example.com'
PASSWORD = 'Cambiar123!'


def seed_rabbit_super_user(apps, schema_editor):
    User = apps.get_model('users', 'User')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')
    Role = apps.get_model('roles', 'Role')

    role = Role.objects.filter(id='RABBIT_SUPER').first()
    if role is None:
        return

    user = User.objects.filter(email=EMAIL).first()
    if user is None:
        hashed_password = bcrypt.hashpw(
            PASSWORD.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        user = User.objects.create(
            email=EMAIL,
            name='Super',
            lastname='Rabbit',
            phone='0000000001',
            password=hashed_password,
            is_active=True,
        )

    UserHasRoles.objects.get_or_create(id_user_id=user.id, id_rol_id=role.id)


def unseed_rabbit_super_user(apps, schema_editor):
    User = apps.get_model('users', 'User')
    UserHasRoles = apps.get_model('users', 'UserHasRoles')

    user = User.objects.filter(email=EMAIL).first()
    if user is None:
        return
    UserHasRoles.objects.filter(id_user_id=user.id, id_rol_id='RABBIT_SUPER').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_line_subscription'),
        ('roles', '0004_seed_rabbit_super_role'),
    ]

    operations = [
        migrations.RunPython(seed_rabbit_super_user, unseed_rabbit_super_user),
    ]
