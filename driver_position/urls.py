from django.urls import path
from .views import create, get_nearby_drivers, driver_detail, delete
urlpatterns =  [
    path('', create),
    path('/nearby/<client_lat>/<client_lng>', get_nearby_drivers),
    path('/delete/<id_driver>', delete),
    path('/<id_driver>', driver_detail),
]