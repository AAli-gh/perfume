from django.urls import path

from . import views

app_name = "notifications"
urlpatterns = [
    path("otp/", views.otp_login, name="otp_login"),
    path("otp/verify/", views.otp_verify, name="otp_verify"),
]
