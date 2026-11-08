from django.db import models


class TimeAndDistanceValues(models.Model):
    id = models.AutoField(primary_key=True)
    km_value = models.FloatField()
    min_value = models.FloatField()
    line = models.OneToOneField(
        'users.Line',
        on_delete=models.CASCADE,
        db_column='id_line',
        null=True,
        blank=True,
        related_name='fare_config',
    )

    class Meta:
        db_table = 'time_and_distance_values'