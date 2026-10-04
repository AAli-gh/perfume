from django.urls import path

from . import views

app_name = "blog"
urlpatterns = [
    path("", views.post_list, name="list"),
    path("<str:slug>/", views.post_detail, name="detail"),
]
