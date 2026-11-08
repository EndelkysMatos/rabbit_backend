import os
import requests
import json
import math
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from client_requests.serializers import ClientRequestsSerializer
from time_and_distance_values.models import TimeAndDistanceValues
from django.db import connection
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from client_requests.models import ClientRequest
from firebase_admin import messaging
from firebase_notification.views import send_push_notification_to_multiple_device
from users.models import User
from users.subscription_service import driver_line_can_receive_new_trips, LINE_SUSPENDED_MESSAGE

GOOGLE_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
MIN_FARE_USD = Decimal('0.80')
MONEY_DECIMALS = Decimal('0.01')


def _normalize_lat_lng(first, second):
    """Accept lat,lng or lng,lat (Flutter sometimes sends lng first in URL paths)."""
    a, b = float(first), float(second)
    if abs(a) > 90 and abs(b) <= 90:
        return b, a
    return a, b


def _haversine_km(lat1, lng1, lat2, lng2):
    """Straight-line distance in km between two coordinates (fallback when Google fails)."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2)
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fallback_distance_matrix(origin_lat, origin_lng, destination_lat, destination_lng):
    distance_km = _haversine_km(origin_lat, origin_lng, destination_lat, destination_lng)
    avg_speed_kmh = 30.0
    duration_min = (distance_km / avg_speed_kmh) * 60 if distance_km > 0 else 0
    duration_sec = max(60, int(round(duration_min * 60)))

    return (
        {
            'status': 'FALLBACK',
            'distance': {
                'text': f"{distance_km:.1f} km",
                'value': int(round(distance_km * 1000)),
            },
            'duration': {
                'text': f"{max(1, int(round(duration_min)))} min",
                'value': duration_sec,
            },
        },
        distance_km,
        duration_min,
    )


def _image_url(image_path):
    if not image_path:
        return None
    if str(image_path).startswith('http://') or str(image_path).startswith('https://'):
        return image_path
    return f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{image_path}"


def _apply_minimum_fare(calculated_fare):
    """Apply business floor and monetary rounding for fare amounts."""
    fare_decimal = Decimal(str(calculated_fare))
    return max(fare_decimal, MIN_FARE_USD).quantize(MONEY_DECIMALS, rounding=ROUND_HALF_UP)


def _validate_and_floor_fare_or_400(raw_value, field_name):
    if raw_value is None:
        return None, Response(
            {'message': f'{field_name} es requerido y debe ser un número válido'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        fare = Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return None, Response(
            {'message': f'{field_name} debe ser un número válido'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if fare <= 0:
        return None, Response(
            {'message': f'{field_name} debe ser mayor a 0'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    fare = _apply_minimum_fare(fare)
    return fare, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    serializer = ClientRequestsSerializer(data=request.data)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if not serializer.is_valid():
        error_messages = []
        for field, errors in serializer.errors.items():  
            for error in errors:
                error_messages.append(f"{field}: {error} ")

        error_response = {
            "message": error_messages,
            "statusCode": status.HTTP_400_BAD_REQUEST
        }
        return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    id_client = data['id_client']
    fare_offered = data['fare_offered']
    pickup_description = data['pickup_description']
    destination_description = data['destination_description']
    pickup_lat = data['pickup_lat']
    pickup_lng = data['pickup_lng']
    destination_lat = data['destination_lat']
    destination_lng = data['destination_lng']

    sql = """
    INSERT INTO client_requests (
      id_client,
      fare_offered,
      pickup_description,
      destination_description,
      pickup_position,
      destination_position,
      status,
      created_at,
      updated_at
    )
    VALUES(
        %s,
        %s,
        %s,
        %s,
        ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat'),
        ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat'),
        'CREATED',
        %s,
        %s
    )
    """



    nearby_drivers_sql = """
        SELECT
           U.id,
           U.notification_token
       FROM
           users AS U
       INNER JOIN
           user_has_roles AS UHR
       ON
           U.id = UHR.id_user AND UHR.id_rol = 'DRIVER'
       INNER JOIN
           drivers_position AS DP
       ON
           U.id = DP.id_driver
       WHERE
           ST_Distance_Sphere(
               DP.position,
               ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat')
           ) < 5000
"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                [
                    id_client,
                    fare_offered,
                    pickup_description,
                    destination_description,
                    pickup_lng,
                    pickup_lat,
                    destination_lng,
                    destination_lat,
                    now,
                    now
                ]
            )
            cursor.execute("SELECT LAST_INSERT_ID()")
            id_client_request = cursor.fetchone()[0]

            cursor.execute(nearby_drivers_sql, [pickup_lng, pickup_lat])
            nearby_drivers = cursor.fetchall()

        notification_tokens = list({
            driver[1]  for driver in nearby_drivers
            if driver[1] is not None and driver[1] != ''
        })
        if notification_tokens:
            send_push_notification_to_multiple_device(
                notification_tokens,
                title="Solicitud de viaje",
                body=pickup_description,
                data={
                    'id_client_request': str(id_client_request),
                    'type': 'CLIENT_REQUEST'
                }
            )

        try:
            from asgiref.sync import async_to_sync
            from socketio_app.sio import sio, get_connected_clients_count
            payload = {'id_client_request': int(id_client_request)}
            async_to_sync(sio.emit)('created_client_request', payload)
            print(
                f"[{datetime.now().isoformat()}] CLIENT_REQUEST_EMIT_OK "
                f"event='created_client_request' connected_clients={get_connected_clients_count()} payload={payload}"
            )
        except Exception as emit_error:
            print(
                f"[{datetime.now().isoformat()}] CLIENT_REQUEST_EMIT_ERROR "
                f"event='created_client_request' payload={{'id_client_request': {id_client_request}}} error={emit_error}"
            )
            return Response(
                {'message': f'Solicitud creada pero falló emisión realtime: {emit_error}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Flutter parses response.data as List (legacy: Response({id}) serialized as [id]).
        return Response([id_client_request], status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'message': f'Error al crear la solicitud de viaje: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _fetch_assigned_trip(cursor, id_client_request):
    """Build the trip detail (client info, route, fares, ETA) right after assignment
    so the driver screen can render without an extra request. Returns None on failure."""
    try:
        detail_sql = """
            SELECT
                CR.id,
                CR.id_client,
                CR.id_driver_assigned,
                CR.fare_offered,
                CR.fare_assigned,
                CR.pickup_description,
                CR.destination_description,
                ST_X(CR.pickup_position) AS pickup_lat,
                ST_Y(CR.pickup_position) AS pickup_lng,
                ST_X(CR.destination_position) AS destination_lat,
                ST_Y(CR.destination_position) AS destination_lng,
                U.name AS client_name,
                U.lastname AS client_lastname,
                U.phone AS client_phone,
                U.image AS client_image
            FROM client_requests AS CR
            INNER JOIN users AS U ON U.id = CR.id_client
            WHERE CR.id = %s
        """
        cursor.execute(detail_sql, [int(id_client_request)])
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(zip(columns, row))

        fallback_dm, distance_km, duration_min = _fallback_distance_matrix(
            d['pickup_lat'], d['pickup_lng'], d['destination_lat'], d['destination_lng']
        )

        return {
            'id_client_request': d['id'],
            'id_client': d['id_client'],
            'id_driver_assigned': d['id_driver_assigned'],
            'fare_offered': d['fare_offered'],
            'fare_assigned': d['fare_assigned'],
            'pickup_description': d['pickup_description'],
            'destination_description': d['destination_description'],
            # Contract: x = lat (ST_X), y = lng (ST_Y).
            'pickup_position': {'x': d['pickup_lat'], 'y': d['pickup_lng']},
            'destination_position': {'x': d['destination_lat'], 'y': d['destination_lng']},
            'client': {
                'name': d['client_name'],
                'lastname': d['client_lastname'],
                'phone': d['client_phone'],
                'image': _image_url(d['client_image']),
            },
            'google_distance_matrix': fallback_dm,
            'distance': distance_km,
            'time_difference': round(duration_min, 2),
        }
    except Exception as fetch_error:
        print(
            f"[{datetime.now().isoformat()}] ASSIGNED_TRIP_FETCH_ERROR "
            f"id_client_request={id_client_request} error={fetch_error}"
        )
        return None


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_driver_assigned(request):
    id = request.data.get('id')
    id_driver_assigned = request.data.get('id_driver_assigned')
    fare_assigned_raw = request.data.get('fare_assigned')

    sql = """
        UPDATE client_requests
        SET 
           id_driver_assigned = %s,
           status = 'ACCEPTED',
           updated_at = NOW(),
           fare_assigned = %s
        WHERE id = %s   
    """
    id_client = request.data.get('id_client')
    try:
        assigned_driver = User.objects.filter(id=id_driver_assigned).first()
        if assigned_driver and not driver_line_can_receive_new_trips(assigned_driver):
            return Response(
                {'message': LINE_SUSPENDED_MESSAGE},
                status=status.HTTP_403_FORBIDDEN,
            )

        fare_assigned_decimal, fare_error = _validate_and_floor_fare_or_400(
            fare_assigned_raw, 'fare_assigned'
        )
        if fare_error:
            return fare_error

        fare_assigned = float(fare_assigned_decimal)
        with connection.cursor() as cursor:
            cursor.execute(sql, [id_driver_assigned, fare_assigned, id])

            # Fetch enriched trip detail so the DRIVER screen can render client info,
            # fare and route immediately from the socket event (no extra slow round-trip).
            trip = _fetch_assigned_trip(cursor, id)

            try:
                from asgiref.sync import async_to_sync
                from socketio_app.sio import sio, get_connected_clients_count
                # Base keys kept identical for the existing client contract.
                payload = {
                    'id_client_request': int(id) if id is not None else None,
                    'id_driver': int(id_driver_assigned) if id_driver_assigned is not None else None,
                    'fare_assigned': fare_assigned,
                    'status': 'ACCEPTED',
                }
                # Extra trip detail (client ignores it; driver uses it to paint the screen).
                if trip:
                    payload['trip'] = trip
                # Same payload broadcast to both the client channel and the driver channel.
                client_event = f"driver_assigned/{id_client}"
                driver_event = f"driver_assigned/{id_driver_assigned}"
                async_to_sync(sio.emit)(client_event, payload)
                async_to_sync(sio.emit)(driver_event, payload)
                print(
                    f"[{datetime.now().isoformat()}] DRIVER_ASSIGNED_EMIT_OK "
                    f"client_event='{client_event}' driver_event='{driver_event}' "
                    f"connected_clients={get_connected_clients_count()} "
                    f"trip_included={bool(trip)} payload={payload}"
                )
            except Exception as emit_error:
                print(
                    f"[{datetime.now().isoformat()}] DRIVER_ASSIGNED_EMIT_ERROR "
                    f"client_event='driver_assigned/{id_client}' "
                    f"driver_event='driver_assigned/{id_driver_assigned}' error={emit_error}"
                )

            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al asignar el conductor : {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_trip_request(request, driver_lat, driver_lng):
    try:
        driver = User.objects.filter(id=request.user.id).first()
        if driver and not driver_line_can_receive_new_trips(driver):
            return Response([], status=status.HTTP_200_OK)

        lat, lng = _normalize_lat_lng(driver_lat, driver_lng)
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                ST_Distance_Sphere(CR.pickup_position, ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat')) AS distance,
                timestampdiff(MINUTE, CR.updated_at, NOW()) AS time_difference,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            WHERE
                timestampdiff(MINUTE, CR.updated_at, NOW()) < 1000 AND status = "CREATED"
            HAVING
                distance < 5000;
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [lng, lat])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            print(
                f"[{datetime.now().isoformat()}] NEARBY_TRIP_RESPONSE "
                f"input_lat={lat} input_lng={lng} count=0 ids=[] "
                f"(no CREATED requests within 5km / 1000 min)"
            )
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        pickup_positions = []
        for result in results:
            result['pickup_position'] = json.loads(result['pickup_position'])
            result['destination_position'] = json.loads(result['destination_position'])
            if result.get('client'):
                result['client'] = json.loads(result['client'])

            if result['client'].get('image'):
                result['client']['image'] = _image_url(result['client']['image'])

            results_json.append(result)
            # In this DB, ST_X = latitude (x), ST_Y = longitude (y).
            # Google Distance Matrix expects "lat,lng", so emit x (lat) first.
            pickup_positions.append(
                f"{result['pickup_position']['x']},{result['pickup_position']['y']}"
            )

        origins = f"{lat},{lng}"
        destinations = "|".join(pickup_positions)
        google_ok = False
        try:
            url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
            params = {
                'destinations': destinations,
                'origins': origins,
                'units': 'metric',
                'key': GOOGLE_API_KEY,
                'mode': 'driving'
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                google_data = response.json()
                if google_data.get('status') == 'OK':
                    elements = google_data.get('rows', [{}])[0].get('elements', [])
                    for index, result in enumerate(results_json):
                        if index < len(elements) and elements[index].get('status') == 'OK':
                            result['google_distance_matrix'] = elements[index]
                            result['distance'] = (elements[index]['distance']['value'] / 1000)
                            result['time_difference'] = round(elements[index]['duration']['value'] / 60, 2)
                        else:
                            # In this DB, ST_X = latitude and ST_Y = longitude => x = lat, y = lng.
                            pickup_lat = result['pickup_position']['x']
                            pickup_lng = result['pickup_position']['y']
                            fallback_dm, distance_km, duration_min = _fallback_distance_matrix(
                                lat, lng, pickup_lat, pickup_lng
                            )
                            result['google_distance_matrix'] = fallback_dm
                            result['distance'] = distance_km
                            result['time_difference'] = round(duration_min, 2)
                    google_ok = True
        except Exception as google_error:
            print(f'Error al consultar Google Distance Matrix (fallback activo): {google_error}')

        if not google_ok:
            for result in results_json:
                # In this DB, ST_X = latitude and ST_Y = longitude => x = lat, y = lng.
                pickup_lat = result['pickup_position']['x']
                pickup_lng = result['pickup_position']['y']
                fallback_dm, distance_km, duration_min = _fallback_distance_matrix(
                    lat, lng, pickup_lat, pickup_lng
                )
                result['google_distance_matrix'] = fallback_dm
                result['distance'] = distance_km
                result['time_difference'] = round(duration_min, 2)

        returned_ids = [r.get('id') for r in results_json]
        print(
            f"[{datetime.now().isoformat()}] NEARBY_TRIP_RESPONSE "
            f"input_lat={lat} input_lng={lng} origins={origins} "
            f"count={len(results_json)} ids={returned_ids} google_ok={google_ok} "
            f"sample={results_json[0].get('google_distance_matrix') if results_json else None}"
        )

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_by_client_request(request, id_client_request):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                CR.id_driver_assigned,
                CR.fare_assigned,
                ST_X(pickup_position) AS pickup_lat,
                ST_Y(pickup_position) AS pickup_lng,
                ST_X(destination_position) AS destination_lat,
                ST_Y(destination_position) AS destination_lng,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client,
                JSON_OBJECT(
                    "name", D.name,
                    "lastname", D.lastname,
                    "phone", D.phone,
                    "image", D.image
                ) AS driver,
                 JSON_OBJECT(
                    "brand", DBI.brand,
                    "color", DBI.color,
                    "plate", DBI.plate
                ) AS bike
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            LEFT JOIN
                 users AS D
            ON 
               D.id = CR.id_driver_assigned
            LEFT JOIN 
                  driver_bike_info AS DBI
            ON 
                 DBI.id_driver = CR.id_driver_assigned
            WHERE
              CR.id = %s  AND status = "ACCEPTED"
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_client_request)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        for result in results:
            if result.get('client'):
                result['client'] = json.loads(result['client'])
                result['driver'] = json.loads(result['driver']) 
                result['pickup_position'] = json.loads(result['pickup_position'])
                result['destination_position'] = json.loads(result['destination_position'])
                result['bike'] = json.loads(result['bike'])

            if result['client'].get('image'):
                result['client']['image'] = _image_url(result['client']['image'])
            
            if result['driver'].get('image'):
                result['driver']['image'] = _image_url(result['driver']['image'])

            # Ensure ETA/recorrido payload is always present for active accepted trip.
            fallback_dm, distance_km, duration_min = _fallback_distance_matrix(
                result['pickup_lat'],
                result['pickup_lng'],
                result['destination_lat'],
                result['destination_lng'],
            )
            result['google_distance_matrix'] = fallback_dm
            result['distance'] = distance_km
            result['time_difference'] = round(duration_min, 2)

            results_json.append(result)

        print(
            f"[{datetime.now().isoformat()}] CLIENT_REQUEST_DETAIL_RESPONSE "
            f"id_client_request={id_client_request} status={results_json[0].get('status')} "
            f"distance={results_json[0].get('distance')} time_difference={results_json[0].get('time_difference')}"
        )
        return Response(results_json[0], status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_by_client_assigned(request, id_client):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                CR.created_at,
                CR.id_driver_assigned,
                CR.fare_assigned,
                CR.client_rating,
                CR.driver_rating,
                ST_X(pickup_position) AS pickup_lng,
                ST_Y(pickup_position) AS pickup_lat,
                ST_X(destination_position) AS destination_lng,
                ST_Y(destination_position) AS destination_lat,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client,
                JSON_OBJECT(
                    "name", D.name,
                    "lastname", D.lastname,
                    "phone", D.phone,
                    "image", D.image
                ) AS driver,
                 JSON_OBJECT(
                    "brand", DBI.brand,
                    "color", DBI.color,
                    "plate", DBI.plate
                ) AS bike
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            LEFT JOIN
                 users AS D
            ON 
               D.id = CR.id_driver_assigned
            LEFT JOIN 
                  driver_bike_info AS DBI
            ON 
                 DBI.id_driver = CR.id_driver_assigned
            WHERE
              CR.id_client = %s  AND status = "FINISHED"
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_client)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        for result in results:
            if result.get('client'):
                result['client'] = json.loads(result['client'])
                result['driver'] = json.loads(result['driver']) 
                result['pickup_position'] = json.loads(result['pickup_position'])
                result['destination_position'] = json.loads(result['destination_position'])
                result['bike'] = json.loads(result['bike'])

            if result['client'].get('image'):
                result['client']['image'] = _image_url(result['client']['image'])
            
            if result['driver'].get('image'):
                result['driver']['image'] = _image_url(result['driver']['image'])

            results_json.append(result)

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_by_driver_assigned(request, id_driver):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                CR.created_at,
                CR.id_driver_assigned,
                CR.fare_assigned,
                CR.client_rating,
                CR.driver_rating,
                ST_X(pickup_position) AS pickup_lng,
                ST_Y(pickup_position) AS pickup_lat,
                ST_X(destination_position) AS destination_lng,
                ST_Y(destination_position) AS destination_lat,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client,
                JSON_OBJECT(
                    "name", D.name,
                    "lastname", D.lastname,
                    "phone", D.phone,
                    "image", D.image
                ) AS driver,
                 JSON_OBJECT(
                    "brand", DBI.brand,
                    "color", DBI.color,
                    "plate", DBI.plate
                ) AS bike
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            LEFT JOIN
                 users AS D
            ON 
               D.id = CR.id_driver_assigned
            LEFT JOIN 
                  driver_bike_info AS DBI
            ON 
                 DBI.id_driver = CR.id_driver_assigned
            WHERE
              CR.id_driver_assigned = %s  AND status = "FINISHED"
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_driver)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        for result in results:
            if result.get('client'):
                result['client'] = json.loads(result['client'])
                result['driver'] = json.loads(result['driver']) 
                result['pickup_position'] = json.loads(result['pickup_position'])
                result['destination_position'] = json.loads(result['destination_position'])
                result['bike'] = json.loads(result['bike'])

            if result['client'].get('image'):
                result['client']['image'] = _image_url(result['client']['image'])
            
            if result['driver'].get('image'):
                result['driver']['image'] = _image_url(result['driver']['image'])

            results_json.append(result)

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_time_and_distance_client_request(request, origin_lat, origin_lng, destination_lat, destination_lng):
    try:
        time_and_distance_values = TimeAndDistanceValues.objects.get(id=1)
        km_value = Decimal(str(time_and_distance_values.km_value))
        min_value = Decimal(str(time_and_distance_values.min_value))

        o_lat, o_lng = _normalize_lat_lng(origin_lat, origin_lng)
        d_lat, d_lng = _normalize_lat_lng(destination_lat, destination_lng)
        origins = f"{o_lat},{o_lng}"
        destinations = f"{d_lat},{d_lng}"
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'destinations': destinations,
            'origins': origins,
            'units': 'metric',
            'key': GOOGLE_API_KEY
        }

        # Try Google first; if anything fails (no internet, timeout, bad key, parse error)
        # fall back to a straight-line estimate so the client can still review and set a fare.
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            if response.status_code != 200 or data.get('status') != 'OK':
                raise ValueError(f"Google status={data.get('status')} http={response.status_code} {data.get('error_message', '')}")

            elements = data.get('rows')[0]['elements'][0]
            if elements.get('status') != 'OK':
                raise ValueError(f"Google element status={elements.get('status')}")

            distance_value = Decimal(str(elements['distance']['value']))
            distance_text = elements['distance']['text']
            duration_value = Decimal(str(elements['duration']['value']))
            duration_text = elements['duration']['text']

            calculated_fare = (
                km_value * (distance_value / Decimal('1000'))
                + min_value * (duration_value / Decimal('60'))
            )
            recommended_value = _apply_minimum_fare(calculated_fare)

            response_data = {
                'recommended_value': float(recommended_value),
                'destination_addresses': data.get('destination_addresses')[0],
                'origin_addresses': data.get('origin_addresses')[0],
                'distance': {
                    'text': distance_text,
                    'value': float((distance_value / Decimal('1000')).quantize(MONEY_DECIMALS, rounding=ROUND_HALF_UP))
                },
                'duration': {
                    'text': duration_text,
                    'value': float((duration_value / Decimal('60')).quantize(MONEY_DECIMALS, rounding=ROUND_HALF_UP))
                },
            }
        except Exception as google_error:
            print(f'Google Distance Matrix no disponible, usando estimación local: {google_error}')
            # Fallback: straight-line distance + assumed average speed (30 km/h).
            distance_km = Decimal(str(_haversine_km(o_lat, o_lng, d_lat, d_lng)))
            avg_speed_kmh = Decimal('30.0')
            duration_min = (distance_km / avg_speed_kmh) * Decimal('60') if distance_km > 0 else Decimal('0')
            calculated_fare = (km_value * distance_km + min_value * duration_min)
            recommended_value = _apply_minimum_fare(calculated_fare)

            response_data = {
                'recommended_value': float(recommended_value),
                'destination_addresses': destinations,
                'origin_addresses': origins,
                'distance': {
                    'text': f"{distance_km:.1f} km",
                    'value': float(distance_km.quantize(MONEY_DECIMALS, rounding=ROUND_HALF_UP))
                },
                'duration': {
                    'text': f"{int(duration_min.quantize(Decimal('1'), rounding=ROUND_HALF_UP))} min",
                    'value': float(duration_min.quantize(MONEY_DECIMALS, rounding=ROUND_HALF_UP))
                },
                'estimated': True,
            }

        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_status(request):
    id_client_request = request.data.get('id_client_request')
    status_data = request.data.get('status')

    try:
        trip = ClientRequest.objects.get(id=id_client_request)
        trip.status = status_data
        if status_data == 'FINISHED':
            trip.finished_at = timezone.now()
        trip.save()
        return Response({'success': True}, status=status.HTTP_200_OK)
    except ClientRequest.DoesNotExist:
        return Response({'message': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'message': f'Error al actualizar el viaje: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_client_rating(request):
    id_client_request = request.data.get('id_client_request')
    client_rating = request.data.get('client_rating')

    sql = """
        UPDATE client_requests
        SET 
           client_rating = %s,
           updated_at = NOW()
        WHERE id = %s   
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [client_rating, id_client_request])
            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al actualizar la calificación: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_driver_rating(request):
    id_client_request = request.data.get('id_client_request')
    driver_rating = request.data.get('driver_rating')

    sql = """
        UPDATE client_requests
        SET 
           driver_rating = %s,
           updated_at = NOW()
        WHERE id = %s   
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [driver_rating, id_client_request])
            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al actualizar la calificación: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)