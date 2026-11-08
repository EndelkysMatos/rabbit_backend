import re
from django.conf import settings
from django.db import connection
from rest_framework.response import Response
from rest_framework import status
from driver_position.models import DriverPosition
from driver_position.serializers import DriverPositionSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from geo_utils import normalize_lat_lng
from users.models import UserHasRoles

DRIVER_ROLE_ID = 'DRIVER'


def _is_active_driver(driver_id):
    return UserHasRoles.objects.filter(
        id_user_id=driver_id,
        id_rol_id=DRIVER_ROLE_ID,
        id_user__is_active=True,
    ).exists()


def _build_image_url(image):
    if not image:
        return None
    return f'http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{image}'


def _fetch_driver_position(id_driver):
    query = """
        SELECT
            DP.id_driver,
            ST_AsText(DP.position) AS position,
            U.name,
            U.lastname,
            U.image
        FROM
            drivers_position AS DP
        INNER JOIN
            users AS U
        ON
            U.id = DP.id_driver
        WHERE
            DP.id_driver = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [id_driver])
        return cursor.fetchone()


def _remove_driver_position(id_driver):
    driver_position = DriverPosition.objects.filter(id_driver=id_driver).first()
    if not driver_position:
        return None
    driver_position.delete()
    return driver_position


def _driver_position_response(id_driver):
    row = _fetch_driver_position(id_driver)
    if not row:
        return Response(
            {
                'id_driver': int(id_driver),
                'lat': None,
                'lng': None,
                'name': None,
                'lastname': None,
                'image': None,
                'exists': False,
                'message': 'Posición de conductor no registrada todavía',
            },
            status=status.HTTP_200_OK,
        )

    position_text = row[1]
    match = re.match(r'POINT\(([-\d.]+) ([-\d.]+)\)', position_text)
    if not match:
        return Response(
            {'message': 'Error al obtener la posición del conductor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    lat, lng = normalize_lat_lng(match.group(1), match.group(2))
    return Response(
        {
            'id_driver': row[0],
            'lat': lat,
            'lng': lng,
            'name': row[2],
            'lastname': row[3],
            'image': _build_image_url(row[4]),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_driver_position(request, id_driver):
    try:
        return _driver_position_response(id_driver)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_drivers(request, client_lat, client_lng):
    try:
        client_lat, client_lng = normalize_lat_lng(client_lat, client_lng)

        query = """
        SELECT
            DP.id_driver,
            ST_AsText(DP.position) AS position,
            ST_Distance_Sphere(
                DP.position,
                ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat')
            ) AS distance
        FROM
            drivers_position AS DP
        INNER JOIN
            users AS U ON U.id = DP.id_driver AND U.is_active = 1
        INNER JOIN
            user_has_roles AS UHR ON UHR.id_user = U.id AND UHR.id_rol = %s
        WHERE
            ST_Distance_Sphere(
                DP.position,
                ST_GeomFromText('POINT(%s %s)', 4326, 'axis-order=long-lat')
            ) <= %s
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [client_lng, client_lat, DRIVER_ROLE_ID, client_lng, client_lat, 5000],
            )
            rows = cursor.fetchall()

        drivers = []
        for row in rows:
            position_text = row[1]
            match = re.match(r'POINT\(([-\d.]+) ([-\d.]+)\)', position_text)
            if match:
                lat, lng = normalize_lat_lng(match.group(1), match.group(2))
                drivers.append({
                    'id_driver': row[0],
                    'position': {'x': lat, 'y': lng},
                    'distance': row[2],
                })

        return Response(drivers, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    serializer = DriverPositionSerializer(data=request.data)
    if serializer.is_valid():
        position = serializer.save()
        return Response(
            {'success': True, 'position': position},
            status=status.HTTP_200_OK,
        )

    error_messages = []
    for field, errors in serializer.errors.items():
        for error in errors:
            error_messages.append(f'{field}: {error} ')

    return Response(
        {'message': error_messages, 'statusCode': status.HTTP_400_BAD_REQUEST},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _delete_driver_position_response(id_driver):
    if not _remove_driver_position(id_driver):
        return Response({'message': 'El conductor no existe'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'message': 'El conductor se ha eliminado'}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete(request, id_driver):
    try:
        return _delete_driver_position_response(id_driver)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def driver_detail(request, id_driver):
    try:
        if request.method == 'GET':
            return _driver_position_response(id_driver)
        return _delete_driver_position_response(id_driver)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
