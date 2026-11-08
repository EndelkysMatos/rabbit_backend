from django.db import migrations


# Tarifa base usada para calcular el valor recomendado del viaje:
#   recommended_value = km_value * km + min_value * minutos
KM_VALUE = 0.5
MIN_VALUE = 0.2


def seed_values(apps, schema_editor):
    TimeAndDistanceValues = apps.get_model(
        'time_and_distance_values', 'TimeAndDistanceValues'
    )
    TimeAndDistanceValues.objects.update_or_create(
        id=1,
        defaults={'km_value': KM_VALUE, 'min_value': MIN_VALUE},
    )


def unseed_values(apps, schema_editor):
    TimeAndDistanceValues = apps.get_model(
        'time_and_distance_values', 'TimeAndDistanceValues'
    )
    TimeAndDistanceValues.objects.filter(id=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('time_and_distance_values', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_values, unseed_values),
    ]
