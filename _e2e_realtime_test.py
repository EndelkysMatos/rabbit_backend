import os
import json
import asyncio
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoRabbitServer.settings')
import django

django.setup()

from users.models import User
from rest_framework.test import APIRequestFactory
from client_requests.views import create as create_client_request
from driver_trip_offers.views import create as create_offer, find_by_client_request
from socketio_app import sio as sio_module
from firebase_notification import views as fcm_views

# Avoid external FCM in test
fcm_views.send_push_notification_to_multiple_device = lambda *a, **k: None

events = []
orig_emit = sio_module.sio.emit

async def capture_emit(event, data=None, *args, **kwargs):
    events.append({
        'ts': datetime.now().isoformat(),
        'event': event,
        'payload': data,
        'target': kwargs.get('to', 'broadcast')
    })
    return await orig_emit(event, data, *args, **kwargs)

sio_module.sio.emit = capture_emit

users = list(User.objects.all()[:2])
if len(users) < 2:
    raise RuntimeError('Need at least 2 users in DB')

client_user, driver_user = users[0], users[1]
client_user.is_authenticated = True
driver_user.is_authenticated = True

factory = APIRequestFactory()

# 1) Client creates request
req_create = factory.post('/client-requests', {
    'id_client': client_user.id,
    'fare_offered': 2.0,
    'pickup_description': 'A',
    'destination_description': 'B',
    'pickup_lat': 9.3700,
    'pickup_lng': -70.7300,
    'destination_lat': 9.3904,
    'destination_lng': -70.7318,
}, format='json')
req_create.user = client_user
res_create = create_client_request(req_create)

if res_create.status_code != 201:
    print('CREATE_CLIENT_REQUEST_FAILED', res_create.status_code, res_create.data)
    raise SystemExit(1)

id_client_request = res_create.data[0] if isinstance(res_create.data, list) else res_create.data.get('id_client_request')

# 2) Driver creates offer
req_offer = factory.post('/driver-trip-offers', {
    'id_driver': driver_user.id,
    'id_client_request': id_client_request,
    'fare_offered': 2.5,
    'time': 4.0,
    'distance': 1.2,
}, format='json')
req_offer.user = driver_user
res_offer = create_offer(req_offer)

# 3) Client query offers
req_find = factory.get(f'/driver-trip-offers/findByClientRequest/{id_client_request}')
req_find.user = client_user
res_find = find_by_client_request(req_find, id_client_request)

print('CREATE_CLIENT_REQUEST', res_create.status_code, res_create.data)
print('CREATE_DRIVER_OFFER', res_offer.status_code, res_offer.data)
print('FIND_OFFERS', res_find.status_code, len(res_find.data) if isinstance(res_find.data, list) else res_find.data)
print('EMIT_LOGS_START')
for e in events:
    print(json.dumps(e, default=str))
print('EMIT_LOGS_END')
