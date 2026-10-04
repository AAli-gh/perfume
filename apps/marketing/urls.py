from django.urls import path

from . import views

app_name = "marketing"
urlpatterns = [
    path("newsletter/", views.newsletter, name="newsletter"),
]
