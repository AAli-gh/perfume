from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.cache import cache_control

from .meta import base_url

# بخش‌های خصوصی؛ صفحه‌های فیلتر و جستجو با meta robots=noindex مدیریت می‌شوند (نه Disallow)، تا گوگل
# بتواند noindex را ببیند.
DISALLOW = ["/studio/", "/cart/", "/orders/", "/account/", "/payments/", "/wishlist/"]


@cache_control(max_age=3600, public=True)
def robots_txt(request):
    lines = ["User-agent: *"]
    if getattr(settings, "SEO_NOINDEX", False):
        lines.append("Disallow: /")  # محیط staging یا آزمایشی
    else:
        # آدرس اختصاصی پنل مدیریت (ADMIN_URL) عمداً در robots.txt نمی‌آید تا فاش نشود
        admin = ["/admin/"] if settings.ADMIN_URL == "admin/" else []
        lines += [f"Disallow: {path}" for path in admin + DISALLOW]
        lines += ["", f"Sitemap: {base_url(request)}/sitemap.xml"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
