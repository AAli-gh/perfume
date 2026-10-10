from django.urls import path

from . import ops_views, views

app_name = "builder"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("theme/", views.theme_editor, name="theme"),
    path("theme/<slug:panel>/", views.theme_editor, name="theme_panel"),
    path("pages/", views.page_list, name="pages"),
    path("pages/<int:pk>/", views.page_editor, name="page"),
    path("pages/<int:pk>/reorder/", views.section_reorder, name="section_reorder"),
    path("pages/<int:pk>/sections/add/", views.section_add, name="section_add"),
    path("pages/<int:pk>/sections/<int:section_pk>/", views.section_edit, name="section"),
    path("pages/<int:pk>/sections/<int:section_pk>/move/", views.section_move, name="section_move"),
    path("pages/<int:pk>/sections/<int:section_pk>/toggle/", views.section_toggle, name="section_toggle"),
    path("pages/<int:pk>/sections/<int:section_pk>/delete/", views.section_delete, name="section_delete"),
    path("preview/", views.preview_page, name="preview"),
    path("preview/exit/", views.preview_exit, name="preview_exit"),
    path("preview/link/", views.preview_link, name="preview_link"),
    path("preview/s/<str:token>/", views.preview_share, name="preview_share"),
    path("publish/", views.publish, name="publish"),
    path("discard/", views.discard, name="discard"),
    path("history/", views.history, name="history"),
    path("reports/", views.sales_report, name="reports"),
    path("orders/", ops_views.orders, name="orders"),
    path("orders/print/", ops_views.print_orders, name="print_orders"),
    path("orders/status/", ops_views.orders_status, name="orders_status"),
    path("orders/tracking/", ops_views.tracking, name="tracking"),
    path("stock/", ops_views.stock, name="stock"),
    path("history/<int:number>/restore/", views.restore, name="restore"),
]
