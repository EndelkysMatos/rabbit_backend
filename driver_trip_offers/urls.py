from django.urls import path
from .views import create, find_by_client_request
urlpatterns =  [
    path('', create),
    path('/findByClientRequest/<id_client_request>', find_by_client_request),
]