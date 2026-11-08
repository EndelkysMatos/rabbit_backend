from django.urls import path
from .views import (
    update,
    updateWithImage,
    get_user_by_id,
    get_all_users,
    update_notification_token,
    update_notification_token_without_id,
)
urlpatterns =  [
    path('<int:id_user>', update),
    path('get/<int:id_user>', get_user_by_id),
    path('all', get_all_users),
    path('upload/<id_user>', updateWithImage),
    # Official route
    path('notification_token/<id_user>', update_notification_token),
    # Compatibility aliases for current Flutter fallbacks
    path('/notification_token/<id_user>', update_notification_token),
    path('notification-token/<id_user>', update_notification_token),
    path('/notification-token/<id_user>', update_notification_token),
    path('notification_token', update_notification_token_without_id),
    path('/notification_token', update_notification_token_without_id),
    path('notification-token', update_notification_token_without_id),
    path('/notification-token', update_notification_token_without_id),
    #path('/login', login )
]