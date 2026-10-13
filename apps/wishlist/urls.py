from django.urls import path

from . import views

app_name = "wishlist"
urlpatterns = [
    path("wishlist/<int:product_id>/toggle/", views.toggle_view, name="toggle"),
    path("account/wishlist/", views.list_view, name="list"),
    path("account/wishlist/<int:product_id>/price-alert/", views.price_alert_view, name="price_alert"),
]
