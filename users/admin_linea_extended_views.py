import csv
import io
import re
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connection
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from client_requests.models import ClientRequest
from time_and_distance_values.models import TimeAndDistanceValues
from users.admin_linea_views import (
    DRIVER_ROLE_ID,
    _admin_or_403,
    _image_url,
)
from users.models import User
from geo_utils import normalize_lat_lng
from users.subscription_service import build_line_payload, build_subscription_payload

MIN_FARE_USD = Decimal('0.80')
VALID_TRIP_STATUSES = {choice[0] for choice in ClientRequest.STATUS}
# "Hoy" del dashboard usa America/Caracas (Venezuela), independiente de TIME_ZONE global (UTC).
DASHBOARD_TIMEZONE = ZoneInfo('America/Caracas')
IN_PROGRESS_STATUSES = ['ACCEPTED', 'ON_THE_WAY', 'ARRIVED', 'TRAVELLING']


def _caracas_today_window():
    """Inclusive start, exclusive end — día calendario en America/Caracas."""
    now_caracas = timezone.now().astimezone(DASHBOARD_TIMEZONE)
    start = now_caracas.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _line_finished_trips_qs(admin):
    return _trip_list_queryset(admin).filter(status='FINISHED')


def _finished_trips_today_qs(admin):
    """Viajes finalizados hoy (día calendario America/Caracas)."""
    start, end = _caracas_today_window()
    today = timezone.now().astimezone(DASHBOARD_TIMEZONE).date().isoformat()
    # Rango UTC para timestamps correctos; DATE() cubre finished_at guardado
    # como hora local MySQL (NOW()) que Django interpreta como UTC.
    return _line_finished_trips_qs(admin).extra(
        where=[
            """(
                (client_requests.finished_at >= %s AND client_requests.finished_at < %s)
                OR DATE(COALESCE(client_requests.finished_at, client_requests.updated_at)) = %s
            )"""
        ],
        params=[start, end, today],
    )


def _line_trip_q(admin):
    """Trips tied to the admin line via assigned driver, offers, or drivers they created."""
    return (
        Q(id_driver_assigned__line_id=admin.line_id)
        | Q(id_driver_assigned__created_by_admin_linea=admin)
        | Q(drivertripoffer__id_driver__line_id=admin.line_id)
    )


def _parse_status_filter(request):
    raw = request.query_params.get('status')
    if raw is None or raw == '':
        return None, None
    normalized = str(raw).strip().upper()
    if normalized not in VALID_TRIP_STATUSES:
        return None, Response(
            {'message': f'status debe ser uno de: {", ".join(sorted(VALID_TRIP_STATUSES))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return normalized, None


def _caracas_day_start(date_value):
    return datetime.combine(date_value, datetime.min.time(), tzinfo=DASHBOARD_TIMEZONE)


def _caracas_day_end_exclusive(date_value):
    return _caracas_day_start(date_value) + timedelta(days=1)


def _coerce_filter_date(value):
    if value is None:
        return None
    if hasattr(value, 'hour'):
        return value.date()
    return value


def _parse_date_range(request):
    date_from = request.query_params.get('from') or request.query_params.get('date_from')
    date_to = request.query_params.get('to') or request.query_params.get('date_to')

    parsed_from = None
    parsed_to = None

    if date_from:
        raw_from = parse_date(str(date_from).strip()) or parse_datetime(str(date_from).strip())
        if raw_from is None:
            return None, None, Response(
                {'message': 'from debe ser fecha ISO (YYYY-MM-DD o datetime)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_from = _coerce_filter_date(raw_from)

    if date_to:
        raw_to = parse_date(str(date_to).strip()) or parse_datetime(str(date_to).strip())
        if raw_to is None:
            return None, None, Response(
                {'message': 'to debe ser fecha ISO (YYYY-MM-DD o datetime)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_to = _coerce_filter_date(raw_to)

    if parsed_from and parsed_to and parsed_from > parsed_to:
        return None, None, Response(
            {'message': 'from no puede ser posterior a to'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return parsed_from, parsed_to, None


def _apply_created_at_date_filters(qs, date_from=None, date_to=None):
    if date_from:
        qs = qs.filter(created_at__gte=_caracas_day_start(date_from))
    if date_to:
        qs = qs.filter(created_at__lt=_caracas_day_end_exclusive(date_to))
    return qs


def _build_user_search_q(search):
    q = (
        Q(name__icontains=search)
        | Q(lastname__icontains=search)
        | Q(email__icontains=search)
        | Q(phone__icontains=search)
    )
    tokens = [part for part in search.split() if part]
    if len(tokens) >= 2:
        q |= Q(name__icontains=tokens[0], lastname__icontains=' '.join(tokens[1:]))
    return q


def _build_trip_search_q(search):
    q = (
        Q(id_client__name__icontains=search)
        | Q(id_client__lastname__icontains=search)
        | Q(id_client__email__icontains=search)
        | Q(id_client__phone__icontains=search)
        | Q(id_driver_assigned__name__icontains=search)
        | Q(id_driver_assigned__lastname__icontains=search)
        | Q(pickup_description__icontains=search)
        | Q(destination_description__icontains=search)
    )
    tokens = [part for part in search.split() if part]
    if len(tokens) >= 2:
        q |= Q(id_client__name__icontains=tokens[0], id_client__lastname__icontains=' '.join(tokens[1:]))
        q |= Q(
            id_driver_assigned__name__icontains=tokens[0],
            id_driver_assigned__lastname__icontains=' '.join(tokens[1:]),
        )
    return q


def _parse_search_filter(request):
    raw = request.query_params.get('search') or request.query_params.get('q')
    if raw is None:
        return None
    normalized = str(raw).strip()
    return normalized or None


def _trip_list_queryset(admin, trip_status=None, date_from=None, date_to=None, search=None):
    qs = ClientRequest.objects.filter(_line_trip_q(admin)).distinct()
    if trip_status:
        qs = qs.filter(status=trip_status)
    qs = _apply_created_at_date_filters(qs, date_from, date_to)
    if search:
        qs = qs.filter(_build_trip_search_q(search))
    return qs


def _trip_list_queryset_detailed(admin, trip_status=None, date_from=None, date_to=None, search=None):
    return (
        _trip_list_queryset(admin, trip_status, date_from, date_to, search)
        .select_related('id_client', 'id_driver_assigned')
        .order_by('-updated_at')
    )


def _coords_from_trip(trip):
    pickup = trip.pickup_position
    destination = trip.destination_position
    return {
        'pickup_position': {'x': pickup.x, 'y': pickup.y},
        'destination_position': {'x': destination.x, 'y': destination.y},
    }


def _trip_summary_payload(trip):
    client = trip.id_client
    driver = trip.id_driver_assigned
    coords = _coords_from_trip(trip)
    revenue = trip.fare_assigned if trip.status == 'FINISHED' and trip.fare_assigned is not None else None
    return {
        'id': trip.id,
        'status': trip.status,
        'fare_offered': trip.fare_offered,
        'fare_assigned': trip.fare_assigned,
        'revenue': revenue,
        'pickup_description': trip.pickup_description,
        'destination_description': trip.destination_description,
        'pickup_position': coords['pickup_position'],
        'destination_position': coords['destination_position'],
        'client_rating': trip.client_rating,
        'driver_rating': trip.driver_rating,
        'created_at': trip.created_at,
        'updated_at': trip.updated_at,
        'client': {
            'id': client.id,
            'name': client.name,
            'lastname': client.lastname,
            'phone': client.phone,
            'image': _image_url(client.image),
        },
        'driver': None
        if not driver
        else {
            'id': driver.id,
            'name': driver.name,
            'lastname': driver.lastname,
            'phone': driver.phone,
            'image': _image_url(driver.image),
            'line_id': driver.line_id,
        },
    }


def _trip_belongs_to_admin_line(trip, admin):
    driver = trip.id_driver_assigned
    if driver and driver.line_id == admin.line_id:
        return True
    if driver and driver.created_by_admin_linea_id == admin.id:
        return True
    return trip.drivertripoffer_set.filter(id_driver__line_id=admin.line_id).exists()


def _get_fare_config_for_line(line_id):
    line_fare = TimeAndDistanceValues.objects.filter(line_id=line_id).first()
    if line_fare:
        return line_fare, False
    global_fare = TimeAndDistanceValues.objects.filter(line__isnull=True).order_by('id').first()
    if global_fare:
        return global_fare, True
    return None, True


def _fare_payload(line, fare_row, is_global_fallback):
    return {
        'line': {'id': line.id, 'name': line.name},
        'km_value': fare_row.km_value if fare_row else 0.5,
        'min_value': fare_row.min_value if fare_row else 0.2,
        'min_fare_usd': float(MIN_FARE_USD),
        'uses_global_fallback': is_global_fallback,
        'source': 'global' if is_global_fallback else 'line',
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_linea_line(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    line = admin.line
    fare_row, is_fallback = _get_fare_config_for_line(admin.line_id)
    line_payload = build_line_payload(line)
    line_payload['km_value'] = fare_row.km_value if fare_row else 0.5
    line_payload['min_value'] = fare_row.min_value if fare_row else 0.2
    line_payload['fare'] = _fare_payload(line, fare_row, is_fallback)
    return Response(line_payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_linea_subscription(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    return Response(build_subscription_payload(admin.line_id), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_linea_reports_summary(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    base_qs = _trip_list_queryset(admin)
    finished_qs = _line_finished_trips_qs(admin)
    finished_today_qs = _finished_trips_today_qs(admin)

    revenue_total = finished_qs.aggregate(total=Sum('fare_assigned'))['total'] or 0
    revenue_today = finished_today_qs.aggregate(total=Sum('fare_assigned'))['total'] or 0

    drivers_active = User.objects.filter(
        line_id=admin.line_id,
        is_active=True,
        userhasroles__id_rol_id=DRIVER_ROLE_ID,
    ).distinct().count()
    drivers_inactive = User.objects.filter(
        line_id=admin.line_id,
        is_active=False,
        userhasroles__id_rol_id=DRIVER_ROLE_ID,
    ).distinct().count()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(DISTINCT DP.id_driver)
            FROM drivers_position DP
            INNER JOIN users U ON U.id = DP.id_driver
            INNER JOIN user_has_roles UHR ON UHR.id_user = U.id AND UHR.id_rol = %s
            WHERE U.id_line = %s AND U.is_active = 1
            """,
            [DRIVER_ROLE_ID, admin.line_id],
        )
        drivers_on_map = cursor.fetchone()[0]

    fare_row, _ = _get_fare_config_for_line(admin.line_id)
    day_start, day_end = _caracas_today_window()
    line_payload = build_line_payload(admin.line)
    line_payload['km_value'] = fare_row.km_value if fare_row else 0.5
    line_payload['min_value'] = fare_row.min_value if fare_row else 0.2

    return Response(
        {
            'line': line_payload,
            'drivers': {
                'active': drivers_active,
                'inactive': drivers_inactive,
                'with_live_position': drivers_on_map,
            },
            'trips': {
                'total': base_qs.count(),
                'created': base_qs.filter(status='CREATED').count(),
                'in_progress': base_qs.filter(status__in=IN_PROGRESS_STATUSES).count(),
                'finished': finished_qs.count(),
                'cancelled': base_qs.filter(status='CANCELLED').count(),
                'today': finished_today_qs.count(),
            },
            'revenue': {
                'total_finished_usd': round(float(revenue_total), 2),
                'today_finished_usd': round(float(revenue_today), 2),
            },
            'meta': {
                'timezone': 'America/Caracas',
                'today_start': day_start.isoformat(),
                'today_end': day_end.isoformat(),
                'finished_at_field': 'finished_at',
            },
            'generated_at': timezone.now(),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_admin_linea_trips(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    trip_status, status_error = _parse_status_filter(request)
    if status_error:
        return status_error

    date_from, date_to, date_error = _parse_date_range(request)
    if date_error:
        return date_error

    search = _parse_search_filter(request)

    try:
        limit = min(int(request.query_params.get('limit', 50)), 200)
        offset = max(int(request.query_params.get('offset', 0)), 0)
    except ValueError:
        return Response({'message': 'limit y offset deben ser enteros'}, status=status.HTTP_400_BAD_REQUEST)

    qs = _trip_list_queryset_detailed(admin, trip_status, date_from, date_to, search)
    total = qs.count()
    trips = qs[offset : offset + limit]

    return Response(
        {
            'count': total,
            'limit': limit,
            'offset': offset,
            'results': [_trip_summary_payload(trip) for trip in trips],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_linea_trip_detail(request, id_trip):
    admin, err = _admin_or_403(request)
    if err:
        return err

    trip = (
        ClientRequest.objects.filter(id=id_trip)
        .select_related('id_client', 'id_driver_assigned')
        .first()
    )
    if not trip:
        return Response({'message': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if not _trip_belongs_to_admin_line(trip, admin):
        return Response({'message': 'No puedes ver viajes fuera de tu línea'}, status=status.HTTP_403_FORBIDDEN)

    payload = _trip_summary_payload(trip)
    offers = []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DTO.id, DTO.fare_offered, DTO.time, DTO.distance, DTO.created_at,
                   U.id, U.name, U.lastname
            FROM driver_trip_offers DTO
            INNER JOIN users U ON U.id = DTO.id_driver
            WHERE DTO.id_client_request = %s AND U.id_line = %s
            ORDER BY DTO.created_at DESC
            """,
            [trip.id, admin.line_id],
        )
        for row in cursor.fetchall():
            offers.append(
                {
                    'id': row[0],
                    'fare_offered': row[1],
                    'time': row[2],
                    'distance': row[3],
                    'created_at': row[4],
                    'driver': {'id': row[5], 'name': row[6], 'lastname': row[7]},
                }
            )

    payload['offers'] = offers
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_admin_linea_trips_csv(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    trip_status, status_error = _parse_status_filter(request)
    if status_error:
        return status_error

    date_from, date_to, date_error = _parse_date_range(request)
    if date_error:
        return date_error

    search = _parse_search_filter(request)
    trips = _trip_list_queryset_detailed(admin, trip_status, date_from, date_to, search)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            'id',
            'status',
            'fare_offered',
            'fare_assigned',
            'revenue',
            'pickup_description',
            'destination_description',
            'client_id',
            'client_name',
            'client_phone',
            'driver_id',
            'driver_name',
            'driver_rating',
            'client_rating',
            'created_at',
            'updated_at',
        ]
    )
    for trip in trips.iterator():
        client = trip.id_client
        driver = trip.id_driver_assigned
        revenue = trip.fare_assigned if trip.status == 'FINISHED' else ''
        writer.writerow(
            [
                trip.id,
                trip.status,
                trip.fare_offered,
                trip.fare_assigned,
                revenue,
                trip.pickup_description,
                trip.destination_description,
                client.id,
                f'{client.name} {client.lastname}'.strip(),
                client.phone,
                driver.id if driver else '',
                f'{driver.name} {driver.lastname}'.strip() if driver else '',
                trip.driver_rating,
                trip.client_rating,
                trip.created_at,
                trip.updated_at,
            ]
        )

    response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="admin_linea_trips.csv"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_admin_linea_driver_positions(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    query = """
        SELECT
            DP.id_driver,
            ST_AsText(DP.position) AS position,
            U.name,
            U.lastname,
            U.phone,
            U.image,
            U.is_active
        FROM drivers_position DP
        INNER JOIN users U ON U.id = DP.id_driver
        INNER JOIN user_has_roles UHR ON UHR.id_user = U.id AND UHR.id_rol = %s
        WHERE U.id_line = %s
        ORDER BY U.name, U.lastname
    """
    results = []
    with connection.cursor() as cursor:
        cursor.execute(query, [DRIVER_ROLE_ID, admin.line_id])
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            item = dict(zip(columns, row))
            position_text = item['position']
            lat = None
            lng = None
            match = re.match(r'POINT\(([-\d.]+) ([-\d.]+)\)', position_text or '')
            if match:
                lat, lng = normalize_lat_lng(match.group(1), match.group(2))
            results.append(
                {
                    'id_driver': item['id_driver'],
                    'lat': lat,
                    'lng': lng,
                    'name': item['name'],
                    'lastname': item['lastname'],
                    'phone': item['phone'],
                    'image': _image_url(item['image']),
                    'is_active': bool(item['is_active']),
                }
            )

    return Response(results, status=status.HTTP_200_OK)


def _filtered_clients_qs(admin, date_from=None, date_to=None, search=None):
    trip_ids = (
        _trip_list_queryset(admin, date_from=date_from, date_to=date_to)
        .values_list('id_client_id', flat=True)
        .distinct()
    )
    clients_qs = User.objects.filter(id__in=trip_ids)
    if search:
        clients_qs = clients_qs.filter(_build_user_search_q(search))
    return clients_qs.distinct()


def _client_summary_payload(admin, client, date_from=None, date_to=None):
    client_trips = _trip_list_queryset(admin, date_from=date_from, date_to=date_to).filter(
        id_client=client
    )
    finished = client_trips.filter(status='FINISHED').count()
    return {
        'id': client.id,
        'name': client.name,
        'lastname': client.lastname,
        'email': client.email,
        'phone': client.phone,
        'image': _image_url(client.image),
        'trip_count': client_trips.count(),
        'finished_trip_count': finished,
        'last_trip_at': client_trips.order_by('-updated_at').values_list('updated_at', flat=True).first(),
    }


def _paginated_client_summaries(admin, date_from, date_to, search, limit, offset):
    clients = list(_filtered_clients_qs(admin, date_from, date_to, search))
    summaries = [_client_summary_payload(admin, client, date_from, date_to) for client in clients]
    summaries.sort(key=lambda item: item['last_trip_at'] or '', reverse=True)
    total = len(summaries)
    return total, summaries[offset : offset + limit]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_admin_linea_clients(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    date_from, date_to, date_error = _parse_date_range(request)
    if date_error:
        return date_error

    search = _parse_search_filter(request)

    try:
        limit = min(int(request.query_params.get('limit', 50)), 200)
        offset = max(int(request.query_params.get('offset', 0)), 0)
    except ValueError:
        return Response({'message': 'limit y offset deben ser enteros'}, status=status.HTTP_400_BAD_REQUEST)

    total, results = _paginated_client_summaries(
        admin, date_from, date_to, search, limit, offset
    )

    return Response(
        {'count': total, 'limit': limit, 'offset': offset, 'results': results},
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_admin_linea_clients_csv(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    date_from, date_to, date_error = _parse_date_range(request)
    if date_error:
        return date_error

    search = _parse_search_filter(request)
    clients = list(_filtered_clients_qs(admin, date_from, date_to, search))
    summaries = [_client_summary_payload(admin, client, date_from, date_to) for client in clients]
    summaries.sort(key=lambda item: item['last_trip_at'] or '', reverse=True)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            'id',
            'name',
            'lastname',
            'email',
            'phone',
            'trip_count',
            'finished_trip_count',
            'last_trip_at',
        ]
    )
    for item in summaries:
        writer.writerow(
            [
                item['id'],
                item['name'],
                item['lastname'],
                item['email'],
                item['phone'],
                item['trip_count'],
                item['finished_trip_count'],
                item['last_trip_at'],
            ]
        )

    response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="admin_linea_clients.csv"'
    return response


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_linea_fares(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    line = admin.line
    if request.method == 'GET':
        fare_row, is_fallback = _get_fare_config_for_line(admin.line_id)
        return Response(_fare_payload(line, fare_row, is_fallback), status=status.HTTP_200_OK)

    km_value = request.data.get('km_value')
    min_value = request.data.get('min_value')

    if km_value is None and min_value is None:
        return Response(
            {'message': 'km_value o min_value son obligatorios para actualizar'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        if km_value is not None:
            km_value = float(km_value)
            if km_value < 0:
                raise ValueError
        if min_value is not None:
            min_value = float(min_value)
            if min_value < 0:
                raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'message': 'km_value y min_value deben ser números >= 0'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    fare_row, _ = _get_fare_config_for_line(admin.line_id)
    if fare_row and fare_row.line_id == admin.line_id:
        if km_value is not None:
            fare_row.km_value = km_value
        if min_value is not None:
            fare_row.min_value = min_value
        fare_row.save(update_fields=['km_value', 'min_value'])
    else:
        global_fare, _ = _get_fare_config_for_line(admin.line_id)
        fare_row = TimeAndDistanceValues.objects.create(
            line_id=admin.line_id,
            km_value=km_value if km_value is not None else (global_fare.km_value if global_fare else 0.5),
            min_value=min_value if min_value is not None else (global_fare.min_value if global_fare else 0.2),
        )

    return Response(_fare_payload(line, fare_row, False), status=status.HTTP_200_OK)
