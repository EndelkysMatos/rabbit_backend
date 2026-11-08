from django.urls import path

from .admin_linea_views import (

    admin_linea_drivers,

    admin_linea_driver_detail,

    deactivate_driver_by_admin_linea,

    reactivate_driver_by_admin_linea,

    update_admin_linea_profile,

    upload_driver_image_by_admin_linea,

)

from .admin_linea_extended_views import (

    admin_linea_fares,

    admin_linea_reports_summary,

    export_admin_linea_trips_csv,

    export_admin_linea_clients_csv,

    get_admin_linea_line,

    get_admin_linea_subscription,

    get_admin_linea_trip_detail,

    list_admin_linea_clients,

    list_admin_linea_driver_positions,

    list_admin_linea_trips,

)



urlpatterns = [

    path('line', get_admin_linea_line),

    path('line/', get_admin_linea_line),

    path('subscription', get_admin_linea_subscription),

    path('subscription/', get_admin_linea_subscription),

    path('dashboard', admin_linea_reports_summary),

    path('dashboard/', admin_linea_reports_summary),

    path('reports/summary', admin_linea_reports_summary),

    path('reports/summary/', admin_linea_reports_summary),

    path('fares', admin_linea_fares),

    path('fares/', admin_linea_fares),

    path('trips/export', export_admin_linea_trips_csv),

    path('trips/export/', export_admin_linea_trips_csv),

    path('trips/<int:id_trip>', get_admin_linea_trip_detail),

    path('trips/<int:id_trip>/', get_admin_linea_trip_detail),

    path('trips', list_admin_linea_trips),

    path('trips/', list_admin_linea_trips),

    path('clients/export', export_admin_linea_clients_csv),

    path('clients/export/', export_admin_linea_clients_csv),

    path('clients', list_admin_linea_clients),

    path('clients/', list_admin_linea_clients),

    path('drivers/positions', list_admin_linea_driver_positions),

    path('drivers/positions/', list_admin_linea_driver_positions),

    path('drivers', admin_linea_drivers),

    path('drivers/', admin_linea_drivers),

    path('drivers/<int:id_driver>/deactivate', deactivate_driver_by_admin_linea),

    path('drivers/<int:id_driver>/deactivate/', deactivate_driver_by_admin_linea),

    path('drivers/<int:id_driver>/reactivate', reactivate_driver_by_admin_linea),

    path('drivers/<int:id_driver>/reactivate/', reactivate_driver_by_admin_linea),

    path('drivers/<int:id_driver>/upload', upload_driver_image_by_admin_linea),

    path('drivers/<int:id_driver>/upload/', upload_driver_image_by_admin_linea),

    path('drivers/<int:id_driver>', admin_linea_driver_detail),

    path('drivers/<int:id_driver>/', admin_linea_driver_detail),

    path('profile', update_admin_linea_profile),

    path('profile/', update_admin_linea_profile),

]

