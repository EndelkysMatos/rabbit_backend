"""
ASGI config for DjangoRabbitServer project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from socketio_app.sio import sio
from socketio_app.routing import socketio_routes
from django.urls import re_path
from socketio import ASGIApp
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoRabbitServer.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r"^socket.io/", ASGIApp(sio)),
        ])
    )
})
