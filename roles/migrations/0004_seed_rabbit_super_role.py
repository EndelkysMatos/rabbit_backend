from django.db import migrations


ROLE = {
    'id': 'RABBIT_SUPER',
    'name': 'Super Admin Rabbit',
    'image': 'https://cdn-icons-png.flaticon.com/512/1828/1828640.png',
    'route': 'admin/super/home',
}


def seed_rabbit_super_role(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    Role.objects.update_or_create(
        id=ROLE['id'],
        defaults={
            'name': ROLE['name'],
            'image': ROLE['image'],
            'route': ROLE['route'],
        },
    )


def unseed_rabbit_super_role(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    Role.objects.filter(id=ROLE['id']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0003_seed_admin_line_role'),
    ]

    operations = [
        migrations.RunPython(seed_rabbit_super_role, unseed_rabbit_super_role),
    ]
