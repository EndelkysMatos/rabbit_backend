from rest_framework import serializers

class ClientRequestsSerializer(serializers.Serializer):
    id_client = serializers.IntegerField()
    fare_offered = serializers.FloatField()
    pickup_description = serializers.CharField(max_length=255)
    destination_description = serializers.CharField(max_length=255)
    pickup_lat = serializers.FloatField()
    pickup_lng = serializers.FloatField()
    destination_lat = serializers.FloatField()
    destination_lng = serializers.FloatField()