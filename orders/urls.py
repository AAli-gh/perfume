from django.urls import path

from . import views

app_name = "orders"
urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("payment/callback/", views.callback, name="callback"),
    path("payment/test-gateway/<str:authority>/", views.fake_gateway, name="fake_gateway"),
    path("<str:number>/", views.detail, name="detail"),
    path("<str:number>/pay/", views.pay, name="pay"),
]
