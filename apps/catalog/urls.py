from django.urls import path

from . import views

app_name = "catalog"
urlpatterns = [
    path("shop/", views.shop, name="shop"),
    path("collections/", views.collections, name="collections"),
    path("product/<str:slug>/", views.product_detail, name="product"),
]
