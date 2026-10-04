from django.urls import path

from . import views

app_name = "orders"
urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/quote/", views.quote, name="quote"),
    path("<str:number>/", views.detail, name="detail"),
]
