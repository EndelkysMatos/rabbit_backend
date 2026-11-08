from django.conf import settings
from rest_framework import serializers
from roles.models import Role


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'image', 'route']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        image = data.get('image')
        if image and not str(image).startswith('http://') and not str(image).startswith('https://'):
            data['image'] = f'http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{image}'
        return data