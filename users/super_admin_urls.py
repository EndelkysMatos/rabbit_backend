from django.urls import path

from users.super_admin_views import (
    activate_line_subscription,
    delete_line,
    delete_line_by_id,
    line_admins,
    list_lines_for_super_admin,
    patch_line_subscription,
    record_line_payment,
    super_admin_me,
    suspend_line_subscription,
)

urlpatterns = [
    path('me', super_admin_me),
    path('me/', super_admin_me),
    path('delete-line', delete_line_by_id),
    path('delete-line/', delete_line_by_id),
    path('lines', list_lines_for_super_admin),
    path('lines/', list_lines_for_super_admin),
    path('lines/<int:id_line>', delete_line),
    path('lines/<int:id_line>/', delete_line),
    path('lines/<int:id_line>/admins', line_admins),
    path('lines/<int:id_line>/admins/', line_admins),
    path('lines/<int:id_line>/delete', delete_line),
    path('lines/<int:id_line>/delete/', delete_line),
    path('lines/<int:id_line>/subscription', patch_line_subscription),
    path('lines/<int:id_line>/subscription/', patch_line_subscription),
    path('lines/<int:id_line>/subscription/activate', activate_line_subscription),
    path('lines/<int:id_line>/subscription/activate/', activate_line_subscription),
    path('lines/<int:id_line>/subscription/suspend', suspend_line_subscription),
    path('lines/<int:id_line>/subscription/suspend/', suspend_line_subscription),
    path('lines/<int:id_line>/subscription/record-payment', record_line_payment),
    path('lines/<int:id_line>/subscription/record-payment/', record_line_payment),
]
