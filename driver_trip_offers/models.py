from django.db import models

# Create your models here.
class DriverTripOffer(models.Model):
    id = models.AutoField(primary_key=True)
    id_driver = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='id_driver'
    )
    id_client_request = models.ForeignKey(
        'client_requests.ClientRequest',
        on_delete=models.CASCADE,
        db_column='id_client_request'
    )
    fare_offered = models.FloatField()
    time = models.FloatField()
    distance = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'driver_trip_offers'