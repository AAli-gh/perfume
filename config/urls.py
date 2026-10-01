from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.pages.urls")),
    path("", include("apps.marketing.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.reviews.urls")),
    path("cart/", include("apps.cart.urls")),
    path("orders/", include("apps.orders.urls")),
    path("account/", include("apps.accounts.urls")),
    path("blog/", include("apps.blog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
