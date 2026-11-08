from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from users.models import User

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if header.startswith('Bearer Bearer '):
            request.META['HTTP_AUTHORIZATION'] = header.replace(
                'Bearer Bearer ', 'Bearer ', 1
            )
        return super().authenticate(request)

    def get_user(self, validated_token):
        user_id = validated_token.get('id') or validated_token.get('user_id')
        if user_id is None:
            raise AuthenticationFailed(
                'El token no contiene una identificación de usuario reconocible'
            )
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise  AuthenticationFailed('Usuario no encontrado')
        if not getattr(user, 'is_active', True):
            raise AuthenticationFailed('Usuario inactivo')
        from users.subscription_service import line_suspended_block_message

        block_message = line_suspended_block_message(user)
        if block_message:
            raise AuthenticationFailed(block_message)
        return user