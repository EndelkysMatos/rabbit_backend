from django.db import migrations, models


def backfill_finished_at(apps, schema_editor):
    ClientRequest = apps.get_model('client_requests', 'ClientRequest')
    for trip in ClientRequest.objects.filter(status='FINISHED', finished_at__isnull=True).iterator():
        trip.finished_at = trip.updated_at
        trip.save(update_fields=['finished_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('client_requests', '0002_alter_clientrequest_id_driver_assigned'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientrequest',
            name='finished_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill_finished_at, migrations.RunPython.noop),
    ]
