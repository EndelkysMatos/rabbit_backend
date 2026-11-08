from django.db import connection
from rest_framework import serializers
from driver_bike_info.models import DriverBikeInfo
from users.models import User

class DriverBikeInfoSerializer(serializers.ModelSerializer):
    id_driver = serializers.IntegerField()
    brand = serializers.CharField(max_length=30)
    color = serializers.CharField(max_length=30)
    plate = serializers.CharField(max_length=30)

    class Meta:
        model = DriverBikeInfo
        fields = ['id_driver','brand','color', 'plate']

    def create(self, validated_data):
        id_driver = validated_data.get('id_driver')  
        brand = validated_data.get('brand') 
        color = validated_data.get('color')   
        plate = validated_data.get('plate')

        try:
            user_instance = User.objects.get(id=id_driver)
        except User.DoesNotExist:
            raise serializers.ValidationError({'message':'El usuario no existe'})
        
        query = """
            REPLACE INTO driver_bike_info (id_driver, brand, color, plate)
            VALUES (%s, %s, %s, %s)
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [id_driver, brand, color, plate])
            
        return {'id_driver': id_driver, 'brand': brand, 'color': color, 'plate': plate}    