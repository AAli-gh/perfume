from django.urls import path

from . import views

app_name = "catalog"
urlpatterns = [
    path("shop/", views.shop, name="shop"),
    path("collections/", views.collections, name="collections"),
    path("collections/<str:slug>/", views.collection_detail, name="collection"),
    path("category/<str:slug>/", views.category_detail, name="category"),
    path("product/<str:slug>/", views.product_detail, name="product"),
    path("product/<str:slug>/notify-me/", views.notify_me, name="notify_me"),
    path("gift-boxes/", views.gift_boxes, name="gift_boxes"),
    path("search/suggest/", views.search_suggest, name="search_suggest"),
]
