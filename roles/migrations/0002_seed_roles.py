from django.db import migrations


ROLES = [
    {
        'id': 'CLIENT',
        'name': 'Cliente',
        'image': 'https://cdn-icons-png.flaticon.com/512/1077/1077114.png',
        'route': 'client/home',
    },
    {
        'id': 'DRIVER',
        'name': 'Conductor',
        'image': 'https://cdn-icons-png.flaticon.com/512/2972/2972185.png',
        'route': 'driver/home',
    },
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in ROLES:
        Role.objects.update_or_create(
            id=role['id'],
            defaults={
                'name': role['name'],
                'image': role['image'],
                'route': role['route'],
            },
        )


def unseed_roles(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    Role.objects.filter(id__in=[r['id'] for r in ROLES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_roles, unseed_roles),
    ]
