from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from driver_bike_info.models import DriverBikeInfo
from driver_bike_info.serializers import DriverBikeInfoSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    serializer = DriverBikeInfoSerializer(data = request.data)

    if serializer.is_valid():
        driver_bike_info = serializer.save()
        return Response(driver_bike_info, status=status.HTTP_201_CREATED)
    
    error_messages = []
    for field, errors in serializer._errors.items():
        for error in errors:
            error_messages.append(f"{field}: {error} ")

    error_response = {
        "message": error_messages,
        "statusCode": status.HTTP_400_BAD_REQUEST
    }

    return Response(error_response, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def find_by_id_driver(request, id_driver):
    try:
        driver_bike_info = DriverBikeInfo.objects.get(id_driver = id_driver)
        response_data = {
            'id_driver': driver_bike_info.id_driver.id,
            'brand': driver_bike_info.brand,
            'color': driver_bike_info.color,
            'plate': driver_bike_info.plate,
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    except DriverBikeInfo.DoesNotExist:
      return Response({
          'message': 'Información de la moto no encontrada',
          'statusCode': status.HTTP_404_NOT_FOUND
      }, status=status.HTTP_404_NOT_FOUND)