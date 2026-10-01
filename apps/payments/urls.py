from django.urls import path

from . import views

app_name = "payments"
urlpatterns = [
    path("orders/<str:number>/pay/", views.start, name="start"),
    path("payments/callback/<slug:gateway>/", views.callback, name="callback"),
    path("orders/payment/callback/", views.legacy_zarinpal_callback, name="legacy_callback"),
    path("payments/test-gateway/<str:authority>/", views.test_gateway, name="test_gateway"),
]
