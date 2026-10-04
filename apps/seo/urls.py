from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.decorators.cache import cache_page

from . import views
from .sitemaps import SITEMAPS

app_name = "seo"
urlpatterns = [
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", cache_page(3600, key_prefix="sitemap")(sitemap), {"sitemaps": SITEMAPS}, name="sitemap"),
]
