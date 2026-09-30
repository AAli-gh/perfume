from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.AuthPageView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.profile, name="profile"),
]
