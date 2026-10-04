from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.ratelimit import ratelimit

urlpatterns = [
    # ورود پنل مدیریت هم مثل ورود فروشگاه محدودیت تلاش دارد
    path(f"{settings.ADMIN_URL}login/", ratelimit("admin-login", "10/10m")(admin.site.login)),
    path(settings.ADMIN_URL, admin.site.urls),
    path("studio/", include("apps.builder.urls")),
    path("", include("apps.seo.urls")),
    path("", include("apps.pages.urls")),
    path("", include("apps.marketing.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.reviews.urls")),
    path("cart/", include("apps.cart.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.wishlist.urls")),
    path("orders/", include("apps.orders.urls")),
    path("account/", include("apps.accounts.urls")),
    path("account/", include("apps.notifications.urls")),
    path("blog/", include("apps.blog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
