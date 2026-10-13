from django.urls import path

from . import views

app_name = "reviews"
urlpatterns = [
    path("product/<str:slug>/review/", views.create, name="create"),
    path("product/<str:slug>/ask/", views.ask, name="ask"),
]
