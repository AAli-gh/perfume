from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("catalog.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),
    path("account/", include("accounts.urls")),
    path("blog/", include("blog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
