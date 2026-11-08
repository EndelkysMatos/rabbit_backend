from django.urls import path
from .views import get_time_and_distance_client_request, create, get_nearby_trip_request,update_driver_assigned,get_by_client_request,update_status, update_client_rating, update_driver_rating, get_by_client_assigned, get_by_driver_assigned
urlpatterns =  [
    path('/<origin_lat>/<origin_lng>/<destination_lat>/<destination_lng>', get_time_and_distance_client_request),
    path('', create),
    path('/<driver_lat>/<driver_lng>', get_nearby_trip_request),
    path('/updateDriverAssigned', update_driver_assigned),
    path('/update_status', update_status),
    path('/update_client_rating', update_client_rating),
    path('/update_driver_rating', update_driver_rating),
    path('/<id_client_request>', get_by_client_request),
    path('/client/assigned/<id_client>', get_by_client_assigned),
    path('/driver/assigned/<id_driver>', get_by_driver_assigned),
    
]