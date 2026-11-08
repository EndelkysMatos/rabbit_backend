from django.db import migrations


ROLE = {
    'id': 'ADMIN_LINEA',
    'name': 'Administrador de línea',
    'image': 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png',
    'route': 'admin-linea/home',
}


def seed_admin_line_role(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    Role.objects.update_or_create(
        id=ROLE['id'],
        defaults={
            'name': ROLE['name'],
            'image': ROLE['image'],
            'route': ROLE['route'],
        },
    )


def unseed_admin_line_role(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    Role.objects.filter(id=ROLE['id']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('roles', '0002_seed_roles'),
    ]

    operations = [
        migrations.RunPython(seed_admin_line_role, unseed_admin_line_role),
    ]
