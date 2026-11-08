from django.shortcuts import get_object_or_404, render
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework import status
from roles.models import Role
from roles.serializers import RoleSerializer
from users.models import User, UserHasRoles
from users.serializers import UserSerializer
import bcrypt
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from django.conf import settings


def getCustomTokenForUser(user):
    refresh_token = RefreshToken.for_user(user)
    refresh_token['id'] = user.id
    refresh_token['name'] = user.name
    if 'user_id' in refresh_token:
        del refresh_token['user_id']

    access = refresh_token.access_token
    access['id'] = user.id
    access['name'] = user.name
    if 'user_id' in access:
        del access['user_id']

    return refresh_token


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def register(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()

        client_role = get_object_or_404(Role, id='CLIENT')
        UserHasRoles.objects.create(id_user=user, id_rol=client_role)
        roles = Role.objects.filter(userhasroles__id_user=user)
        roles_serializer = RoleSerializer(roles, many=True)

        refresh_token = getCustomTokenForUser(user)
        access_token = str(refresh_token.access_token)

        response_data = {
            "user": {
                "id": user.id,
                "name": user.name,
                "lastname": user.lastname,
                "email": user.email,
                "phone": user.phone,
                "image": f'http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{user.image}' if user.image else None,
                "notification_token": user.notification_token,
                "roles": roles_serializer.data,
            },
            "token": 'Bearer ' + access_token
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    error_messages = []
    for field, errors in serializer._errors.items():
        for error in errors:
            error_messages.append(f"{field}: {error} ")

    error_response = {
        "message": error_messages,
        "statusCode": status.HTTP_400_BAD_REQUEST
    }

    return Response(error_response, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response(
            {
                "message": "El email y la contraseña son obligatorios",
                "statusCode": status.HTTP_400_BAD_REQUEST
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {
                "message": "El email o la contraseña no son válidos",
                "statusCode": status.HTTP_401_UNAUTHORIZED
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not getattr(user, 'is_active', True):
        return Response(
            {
                "message": "Usuario inactivo",
                "statusCode": status.HTTP_403_FORBIDDEN
            },
            status=status.HTTP_403_FORBIDDEN
        )

    if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        from users.subscription_service import line_suspended_block_message

        block_message = line_suspended_block_message(user)
        if block_message:
            return Response(
                {
                    'message': block_message,
                    'statusCode': status.HTTP_403_FORBIDDEN,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh_token = getCustomTokenForUser(user)
        access_token = str(refresh_token.access_token)
        roles = Role.objects.filter(userhasroles__id_user=user)
        roles_serializer = RoleSerializer(roles, many=True)
        user_data = {
            "user": {
                "id": user.id,
                "name": user.name,
                "lastname": user.lastname,
                "email": user.email,
                "phone": user.phone,
                "image": f'http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{user.image}' if user.image else None,
                "notification_token": user.notification_token,
                "roles": roles_serializer.data,
            },
            "token": 'Bearer ' + access_token
        }
        return Response(user_data, status=status.HTTP_200_OK)
    else:
        return Response(
            {
                "message": "El email o la contraseña no son válidos",
                "statusCode": status.HTTP_401_UNAUTHORIZED
            },
            status=status.HTTP_401_UNAUTHORIZED
        )