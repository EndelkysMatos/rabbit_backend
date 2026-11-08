from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_line_and_user_admin_fields'),
        ('time_and_distance_values', '0002_seed_time_and_distance_values'),
    ]

    operations = [
        migrations.AddField(
            model_name='timeanddistancevalues',
            name='line',
            field=models.OneToOneField(
                blank=True,
                db_column='id_line',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='fare_config',
                to='users.line',
            ),
        ),
    ]
