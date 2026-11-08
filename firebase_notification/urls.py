from django.urls import path
from .views import send_notification, send_multiple_notification
urlpatterns =  [

    path('/send/notification', send_notification),
    path('/send/multiple/notification', send_multiple_notification),
    
]