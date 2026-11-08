from django.db import migrations


def update_rabbit_super_role_image(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    Role.objects.filter(id='RABBIT_SUPER').update(
        image='/media/roles/rabbit_super_role.png',
        name='Super Admin Rabbit',
        route='super/home',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0004_seed_rabbit_super_role'),
    ]

    operations = [
        migrations.RunPython(update_rabbit_super_role_image, migrations.RunPython.noop),
    ]
