import socketio
import json
from datetime import datetime
from asgiref.sync import sync_to_async

sio = socketio.AsyncServer(async_mode='asgi')
connected_sids = set()
driver_socket_sessions = {}
trip_position_emit_state = {'minute_key': None, 'count': 0}


def _is_active_driver(driver_id):
    from users.models import UserHasRoles

    try:
        driver_id = int(driver_id)
    except (TypeError, ValueError):
        return False
    return UserHasRoles.objects.filter(
        id_user_id=driver_id,
        id_rol_id='DRIVER',
        id_user__is_active=True,
    ).exists()


def get_connected_clients_count():
    return len(connected_sids)


def _log_emit(event_name, payload, target='broadcast'):
    print(
        f"[{datetime.now().isoformat()}] SOCKET EMIT event='{event_name}' "
        f"target='{target}' connected_clients={get_connected_clients_count()} payload={payload}"
    )


def _to_number(value):
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if text == '':
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _bump_trip_position_counter():
    minute_key = datetime.now().strftime('%Y-%m-%dT%H:%M')
    if trip_position_emit_state['minute_key'] != minute_key:
        trip_position_emit_state['minute_key'] = minute_key
        trip_position_emit_state['count'] = 0
    trip_position_emit_state['count'] += 1
    return trip_position_emit_state['count']


def _resolve_id_client_from_request(id_client_request):
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id_client FROM client_requests WHERE id = %s LIMIT 1",
                [int(id_client_request)],
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else None
    except Exception as e:
        print(
            f"[{datetime.now().isoformat()}] TRIP_POSITION_RESOLVE_CLIENT_ERROR "
            f"id_client_request={id_client_request} error={e}"
        )
        return None


@sio.event
async def connect(sid, environ):
    connected_sids.add(sid)
    print(f'Cliente conectado: {sid}')
    print(f'Clientes conectados activos: {get_connected_clients_count()}')
    await sio.emit('message', {'data': 'conexión exitosa'}, to=sid)


@sio.event
async def disconnect(sid):
    connected_sids.discard(sid)
    print(f'Cliente desconectado: {sid}')
    print(f'Clientes conectados activos: {get_connected_clients_count()}')
    driver_id = driver_socket_sessions.pop(sid, None)
    if driver_id is not None:
        await sio.emit('driver_disconnected', {'id_driver': driver_id})


@sio.event
async def message(sid, data):
    print(f'Datos del Cliente en socket: {sid}: {data}')
    await sio.emit('new_message', data, to=sid)


@sio.event
async def change_driver_position(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return

        driver_id = json_data.get('id')
        lat = _to_number(json_data.get('lat'))
        lng = _to_number(json_data.get('lng'))
        if driver_id is None or lat is None or lng is None:
            raise KeyError('id, lat o lng')

        is_active = await sync_to_async(_is_active_driver, thread_sensitive=True)(driver_id)
        if not is_active:
            print(f'Posición ignorada: conductor inactivo id={driver_id}')
            return

        driver_socket_sessions[sid] = int(driver_id)
        print(f'Emitió nueva posición en socket: {sid}: {data}')
        await sio.emit('new_driver_position', {
            'id': int(driver_id),
            'lat': lat,
            'lng': lng,
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def new_client_request(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return

        print(f'Se emitió  una nueva solicitud en socket: {sid}: {data}')
        payload = {
            'id_socket': sid,
            'id_client_request': json_data['id_client_request'],
        }
        _log_emit('created_client_request', payload)
        await sio.emit('created_client_request', payload)
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def new_driver_offer(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return

        print(f'El conductor  emitió  una nueva oferta en socket: {sid}: {data}')
        event_name = f"created_driver_offer/{json_data['id_client_request']}"
        payload = {
            'id_socket': sid,
            'id_client_request': json_data.get('id_client_request'),
            'id_driver': json_data.get('id_driver'),
            'id_driver_trip_offer': json_data.get('id_driver_trip_offer'),
        }
        _log_emit(event_name, payload)
        await sio.emit(event_name, payload)
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def new_driver_assigned(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return

        print(f'Emitió  una asignación de conductor en socket: {sid}: {data}')
        id_client = json_data.get('id_client')
        if id_client is None:
            raise KeyError('id_client')

        event_name = f"driver_assigned/{id_client}"
        payload = {
            'id_socket': sid,
            'id_client_request': json_data.get('id_client_request'),
            'id_driver': json_data.get('id_driver'),
            'fare_assigned': json_data.get('fare_assigned'),
            'status': json_data.get('status', 'ACCEPTED'),
        }
        _log_emit(event_name, payload)
        await sio.emit(event_name, payload)
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def trip_change_driver_position(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return

        id_client = json_data.get('id_client')
        id_client_request = json_data.get('id_client_request')
        lat = _to_number(json_data.get('lat'))
        lng = _to_number(json_data.get('lng'))

        print(
            f"[{datetime.now().isoformat()}] [IN] trip_change_driver_position "
            f"sid={sid} payload={json_data} id_client={id_client} id_client_request={id_client_request}"
        )

        if id_client is None and id_client_request is not None:
            id_client = await sync_to_async(_resolve_id_client_from_request, thread_sensitive=True)(
                id_client_request
            )

        if id_client is None:
            raise KeyError('id_client or resolvable id_client_request')

        if lat is None or lng is None:
            raise ValueError(f"lat/lng inválidos lat={json_data.get('lat')} lng={json_data.get('lng')}")

        event_name = f"trip_new_driver_position/{int(id_client)}"
        payload = {'lat': lat, 'lng': lng}
        emit_count = _bump_trip_position_counter()

        _log_emit(event_name, payload)
        print(
            f"[{datetime.now().isoformat()}] [OUT] trip_change_driver_position "
            f"event='{event_name}' payload={payload} id_client={id_client} "
            f"id_client_request={id_client_request} emits_this_minute={emit_count}"
        )
        await sio.emit(event_name, payload)
        if id_client_request is not None:
            request_event = f"trip_new_driver_position/{int(id_client_request)}"
            _log_emit(request_event, payload)
            await sio.emit(request_event, payload)
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except Exception as e:
        print(
            f"[{datetime.now().isoformat()}] TRIP_POSITION_EMIT_ERROR sid={sid} "
            f"payload={data} error={e}"
        )


@sio.event
async def update_status_trip(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return

        print(f'Emitió  una asignación de conductor en socket: {sid}: {data}')
        event_name = f"new_status_trip/{json_data['id_client_request']}"
        payload = {
            'id_socket': sid,
            'status': json_data['status'],
            'id_client_request': json_data['id_client_request']
        }
        _log_emit(event_name, payload)
        await sio.emit(event_name, payload)
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')
