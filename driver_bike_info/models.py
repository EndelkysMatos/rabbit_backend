from django.db import models

# Create your models here.
class DriverBikeInfo(models.Model):
    id_driver = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='id_driver'
    )
    brand = models.CharField(max_length=30)
    color = models.CharField(max_length=30)
    plate = models.CharField(max_length=30)

    class Meta:
        db_table = 'driver_bike_info'