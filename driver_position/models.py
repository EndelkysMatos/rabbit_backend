from django.db import models
from django.contrib.gis.db import models as gis_models
# Create your models here.
class DriverPosition(gis_models.Model):
    id_driver = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='id_driver',
        related_name='drivers_position'
    )
    position = gis_models.PointField(
        geography=True,
        spatial_index=True
    )

    class Meta:
        db_table='drivers_position'