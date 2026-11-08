from django.shortcuts import render
from firebase_admin import messaging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# Create your views here.
def send_push_notification(token, title, body, data=None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=token,
        data=data if data else None,
        android=messaging.AndroidConfig(
            priority='high',
            ttl=120
        ),
        apns=messaging.APNSConfig(
            headers={
                'apns-priority': '5',
                'apns-expiration': '120'
            }
        )
    )
    response = messaging.send(message)
    print(f'Notificación enviada exitosamente: {response}')
    return response

def send_push_notification_to_multiple_device(tokens, title, body, data=None):
    if not tokens:
        return None
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        tokens=tokens,
        data=data if data else None,
         android=messaging.AndroidConfig(
            priority='high',
            ttl=120
        ),
        apns=messaging.APNSConfig(
            headers={
                'apns-priority': '5',
                'apns-expiration': '120'
            }
        )
    )
    response = messaging.send_each_for_multicast(message)
    print(f' {response.success_count}  Notificaciones enviadas exitosamente: {response}')
    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_notification(request):
    data = request.data
    token = data.get('token')
    title = data.get('title')
    body = data.get('body')
    notification_data = data.get('data', {})

    if not all([token, title, body]):
        return Response({'message': f'Faltan parámetros para enviar la notificación'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        response = send_push_notification(token, title, body, data)
        return Response({'message': f'Notificación Enviada: {response}'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al enviar la notificación: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_multiple_notification(request):
    data = request.data
    tokens = data.get('tokens')
    title = data.get('title')
    body = data.get('body')
    notification_data = data.get('data', {})

    if not all([tokens, title, body]):
        return Response({'message': f'Faltan parámetros para enviar la notificación'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        response = send_push_notification_to_multiple_device(tokens, title, body, data)
        return Response({'message': f'{response.success_count} Notificaciones enviadas exitosamente'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al enviar la notificación: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)