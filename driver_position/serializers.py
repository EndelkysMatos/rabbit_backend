from django.db import connection
from rest_framework import serializers

from driver_position.models import DriverPosition
from users.models import User, UserHasRoles

DRIVER_ROLE_ID = 'DRIVER'


class DriverPositionSerializer(serializers.ModelSerializer):
    id_driver = serializers.IntegerField()
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)

    class Meta:
        model = DriverPosition
        fields = ['id_driver','lat','lng']

    def create(self, validated_data):
        id_driver = validated_data.get('id_driver')  
        lat = validated_data.get('lat') 
        lng = validated_data.get('lng')   

        try:
            user_instance = User.objects.get(id=id_driver)
        except User.DoesNotExist:
            raise serializers.ValidationError({'message':'El usuario no existe'})

        if not user_instance.is_active:
            raise serializers.ValidationError(
                {'message': 'El conductor no está activo'}
            )
        if not UserHasRoles.objects.filter(
            id_user=user_instance,
            id_rol_id=DRIVER_ROLE_ID,
        ).exists():
            raise serializers.ValidationError(
                {'message': 'El usuario no es un conductor activo'}
            )
        
        query = """
            REPLACE INTO drivers_position (id_driver, position)
            VALUES (%s, ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat'))
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [id_driver, lng, lat])
            
        return {'id_driver': id_driver, 'lat': lat, 'lng': lng}    