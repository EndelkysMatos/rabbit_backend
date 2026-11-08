from django.db import models
from django.contrib.gis.db import models as gis_models
# Create your models here.
class ClientRequest(models.Model):
    STATUS = [
        ('CREATED', 'CREATED'),
        ('ACCEPTED', 'ACCEPTED'),
        ('ON_THE_WAY', 'ON_THE_WAY'),
        ('ARRIVED', 'ARRIVED'),
        ('TRAVELLING', 'TRAVELLING'),
        ('FINISHED', 'FINISHED'),
        ('CANCELLED', 'CANCELLED'),
    ]

    id = models.AutoField(primary_key=True)
    id_client = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='id_client',
        related_name='client_requests'
    )
    id_driver_assigned = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        db_column='id_driver_assigned',
        null=True,
        related_name='driver_requests'
    )
    fare_offered = models.FloatField()
    pickup_description = models.CharField(max_length=255)
    destination_description = models.CharField(max_length=255)
    fare_assigned = models.FloatField(null=True)
    client_rating = models.FloatField(null=True)
    driver_rating = models.FloatField(null=True)
    status = models.CharField(
        choices=STATUS,
        default='CREATED',
        max_length=20
    )
    pickup_position = gis_models.PointField(geography=True, spatial_index=True)
    destination_position = gis_models.PointField(geography=True, spatial_index=True)
    finished_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta: 
        db_table = 'client_requests'
