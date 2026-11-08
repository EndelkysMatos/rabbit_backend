from rest_framework import serializers
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from client_requests.models import ClientRequest
from driver_trip_offers.models import DriverTripOffer
from users.models import User

MIN_FARE_USD = Decimal('0.80')
MONEY_DECIMALS = Decimal('0.01')


class DriverTripOfferSerializer(serializers.ModelSerializer):
    id_driver = serializers.PrimaryKeyRelatedField(
        queryset = User.objects.all(),
        error_messages = {
            'does_not_exist': 'El conductor con ese ID no existe',
            'invalid': 'El valor proporcionado  no es válido',
        }
    )
    id_client_request = serializers.PrimaryKeyRelatedField(
        queryset = ClientRequest.objects.all(),
        error_messages = {
            'does_not_exist': 'La solicitud del cliente con ese ID no existe',
            'invalid': 'El valor proporcionado  no es válido',
        }
    )
    class Meta: 
        model = DriverTripOffer
        fields = [
            'id',
            'id_driver',
            'id_client_request',
            'fare_offered',
            'time',
            'distance',
            'created_at',
            'updated_at'
        ]

    def validate_fare_offered(self, value):
        try:
            fare = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise serializers.ValidationError('fare_offered debe ser un número válido')

        if fare <= 0:
            raise serializers.ValidationError('fare_offered debe ser mayor a 0')

        fare = max(fare, MIN_FARE_USD).quantize(MONEY_DECIMALS, rounding=ROUND_HALF_UP)
        return float(fare)

    def create(self, validated_data):
        driver_trip_offer = DriverTripOffer.objects.create(**validated_data)
        return driver_trip_offer   