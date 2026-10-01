from django.urls import path

from . import views

app_name = "wishlist"
urlpatterns = [
    path("wishlist/<int:product_id>/toggle/", views.toggle_view, name="toggle"),
    path("account/wishlist/", views.list_view, name="list"),
]
