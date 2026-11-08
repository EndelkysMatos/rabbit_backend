from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import connection, transaction
from datetime import datetime
from driver_trip_offers.serializers import DriverTripOfferSerializer
import json
from django.conf import settings
from users.models import User
from users.subscription_service import driver_line_can_receive_new_trips, LINE_SUSPENDED_MESSAGE
# Create your views here.



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def find_by_client_request(request, id_client_request):
    try:
        query = """
           SELECT
              DTO.id,
              DTO.id_client_request,
              DTO.id_driver,
              DTO.fare_offered,
              DTO.time,
              DTO.distance,
              DTO.created_at,
              DTO.updated_at,
              JSON_OBJECT(
                   "name", U.name,
                   "lastname", U.lastname,
                   "phone", U.phone,
                   "image", U.image
              ) AS driver,
              JSON_OBJECT(
                   "brand", DBI.brand,
                   "color", DBI.color,
                   "plate", DBI.plate
              ) AS bike
            FROM 
                driver_trip_offers AS  DTO
            INNER JOIN
                users AS U
            ON
                U.id = DTO.id_driver
            LEFT JOIN 
                driver_bike_info AS DBI
            ON 
                DTO.id_driver = DBI.id_driver
            WHERE 
                DTO.id_client_request = %s             
         """
        
        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_client_request)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)
        

        results_json = []
        for result in results:
            result['driver'] = json.loads(result['driver']) if result['driver'] else {}
            result['bike'] = json.loads(result['bike']) if result['bike'] else {}

            if result['driver'].get('image'):
                result['driver']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['driver']['image']}"

            results_json.append(result)

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
   

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    id_driver = request.data.get('id_driver')
    driver = User.objects.filter(id=id_driver or request.user.id).first()
    if driver and not driver_line_can_receive_new_trips(driver):
        return Response(
            {'message': LINE_SUSPENDED_MESSAGE},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = DriverTripOfferSerializer(data=request.data)
    if serializer.is_valid():
        driver_trip_offer = serializer.save()
        event_name = f"created_driver_offer/{driver_trip_offer.id_client_request_id}"
        payload = {
            'id_client_request': driver_trip_offer.id_client_request_id,
            'id_driver': driver_trip_offer.id_driver_id,
            'id_driver_trip_offer': driver_trip_offer.id,
        }

        try:
            from asgiref.sync import async_to_sync
            from socketio_app.sio import sio, get_connected_clients_count
            async_to_sync(sio.emit)(event_name, payload)
            print(
                f"[{datetime.now().isoformat()}] OFFER_EMIT_OK "
                f"event='{event_name}' connected_clients={get_connected_clients_count()} payload={payload}"
            )
        except Exception as emit_error:
            print(
                f"[{datetime.now().isoformat()}] OFFER_EMIT_ERROR "
                f"event='{event_name}' payload={payload} error={emit_error}"
            )
            return Response(
                {
                    'message': f'Oferta creada pero falló la emisión realtime: {emit_error}',
                    'offer': serializer.data,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    error_messages = []
    for field, errors in serializer._errors.items():
        for error in errors:
            error_messages.append(f"{field}: {error} ")

    error_response = {
        "message": error_messages,
        "statusCode": status.HTTP_400_BAD_REQUEST
    }

    return Response(error_response, status=status.HTTP_400_BAD_REQUEST)