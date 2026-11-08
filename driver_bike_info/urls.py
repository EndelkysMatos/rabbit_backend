from django.urls import path
from .views import create, find_by_id_driver
urlpatterns =  [
    path('', create),
    path('/<id_driver>', find_by_id_driver)

]