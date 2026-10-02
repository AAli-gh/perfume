from django.urls import path

from . import views

app_name = "builder"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("theme/", views.theme_editor, name="theme"),
    path("theme/<slug:panel>/", views.theme_editor, name="theme_panel"),
    path("pages/", views.page_list, name="pages"),
    path("pages/<int:pk>/", views.page_editor, name="page"),
    path("pages/<int:pk>/reorder/", views.section_reorder, name="section_reorder"),
    path("pages/<int:pk>/sections/add/", views.section_add, name="section_add"),
    path("pages/<int:pk>/sections/<int:section_pk>/", views.section_edit, name="section"),
    path("pages/<int:pk>/sections/<int:section_pk>/move/", views.section_move, name="section_move"),
    path("pages/<int:pk>/sections/<int:section_pk>/toggle/", views.section_toggle, name="section_toggle"),
    path("pages/<int:pk>/sections/<int:section_pk>/delete/", views.section_delete, name="section_delete"),
]
