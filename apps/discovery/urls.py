from django.urls import path

from . import views

app_name = "discovery"
urlpatterns = [
    path("compare/", views.compare_page, name="compare"),
    path("compare/<int:product_id>/toggle/", views.compare_toggle, name="compare_toggle"),
    path("compare/<int:product_id>/remove/", views.compare_remove, name="compare_remove"),
    path("compare/clear/", views.compare_clear, name="compare_clear"),
    path("compare/set/", views.compare_set, name="compare_set"),
    path("finder/", views.finder_view, name="finder"),
    path("finder/results/", views.finder_results, name="finder_results"),
    path("finder/reset/", views.finder_reset, name="finder_reset"),
]
