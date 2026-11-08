from socketio import ASGIApp
from socketio_app.sio import sio

socketio_routes = [
    ASGIApp(sio)
]