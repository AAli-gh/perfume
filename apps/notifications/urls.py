from django.urls import path

from . import staff_2fa, views

app_name = "notifications"
urlpatterns = [
    path("otp/", views.otp_login, name="otp_login"),
    path("otp/verify/", views.otp_verify, name="otp_verify"),
    path("staff-verify/", staff_2fa.verify_view, name="staff_2fa"),
]
