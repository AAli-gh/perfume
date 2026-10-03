"""ساخت متاتگ‌های سئو برای هر صفحه: عنوان، توضیح، canonical، robots، Open Graph، Twitter و JSON-LD.

قواعد:
- عنوان/توضیح اختصاصی (SeoFields) ← در غیر این صورت از خود آیتم ← در غیر این صورت پیش‌فرض فروشگاه.
- canonical همیشه آدرس مطلق روی «دامنه اصلی» فروشگاه است (StoreDomain.is_primary)، بدون پارامترهای فیلتر.
- noindex برای: بخش‌های خصوصی (سبد، سفارش، حساب، …)، نتایج فیلتر/جستجو، حالت پیش‌نمایش، آیتم‌های
  علامت‌خورده و محیط‌هایی که SEO_NOINDEX دارند (مثلاً staging).
"""

import re
from dataclasses import dataclass, field

from django.conf import settings
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from . import jsonld

PRIVATE_NAMESPACES = {"cart", "orders", "accounts", "wishlist", "payments", "builder", "reviews", "marketing"}
INDEXABLE_PARAMS = {"page"}
DESCRIPTION_LIMIT = 160
ROBOTS_INDEX = "index, follow, max-image-preview:large"
ROBOTS_NOINDEX = "noindex, follow"


@dataclass
class Seo:
    title: str
    description: str
    canonical: str
    robots: str
    og_type: str = "website"
    image: str = ""
    image_alt: str = ""
    site_name: str = ""
    twitter: str = ""
    verification: dict = field(default_factory=dict)
    jsonld: list = field(default_factory=list)

    @property
    def indexable(self):
        return self.robots.startswith("index")


# ---------- آدرس‌ها ----------

def canonical_host(request):
    """دامنه اصلی فروشگاه (در صورت تعریف) وگرنه همان Host درخواست."""
    cached = getattr(request, "_seo_host", None)
    if cached:
        return cached
    host = request.get_host()
    store = getattr(request, "store", None)
    if store is not None:
        primary = store.domains.filter(is_primary=True).values_list("domain", flat=True).first()
        if primary:
            host = primary
    request._seo_host = host
    return host


def base_url(request):
    return f"{request.scheme}://{canonical_host(request)}"


def absolute(request, url):
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return f"{request.scheme}:{url}"
    return base_url(request) + (url if url.startswith("/") else "/" + url)


# ---------- متن ----------

def clean_text(value, limit=DESCRIPTION_LIMIT):
    text = re.sub(r"\s+", " ", strip_tags(str(value or ""))).strip()
    text = re.sub(r"(^|\s)#+\s*", r"\1", text)  # تیترهای ## متن مقاله
    return Truncator(text).chars(limit, truncate="…") if limit else text


def _image_url(file_field):
    try:
        return file_field.url if file_field else ""
    except ValueError:
        return ""


# ---------- تشخیص نوع آیتم (بدون import مستقیم مدل‌ها برای سادگی) ----------

def _kind(obj):
    return f"{obj._meta.app_label}.{obj._meta.model_name}" if obj is not None and hasattr(obj, "_meta") else ""


def _default_title(obj, kind, site_name, tagline):
    if kind == "catalog.product" or kind in ("catalog.collection", "catalog.category"):
        return f"{obj.name} | {site_name}"
    if kind == "blog.post":
        return f"{obj.title} | مجله {site_name}"
    return f"{site_name} | {tagline}" if tagline else site_name


def _object_description(obj, kind):
    return {
        "catalog.product": lambda: obj.short_description,
        "blog.post": lambda: obj.excerpt,
        "catalog.collection": lambda: obj.tagline,
        "catalog.category": lambda: obj.description,
    }.get(kind, lambda: "")()


def _object_image(obj, kind):
    attr = {"catalog.product": "image", "blog.post": "cover", "catalog.collection": "image"}.get(kind)
    return _image_url(getattr(obj, attr)) if attr else ""


def _is_noindex(request, obj, explicit):
    if explicit or getattr(settings, "SEO_NOINDEX", False) or getattr(request, "is_preview", False):
        return True
    if obj is not None and getattr(obj, "noindex", False):
        return True
    match = getattr(request, "resolver_match", None)
    if match and match.namespace in PRIVATE_NAMESPACES:
        return True
    return any(value for key, value in request.GET.items() if key not in INDEXABLE_PARAMS)


def _canonical(request, noindex_by_params):
    url = base_url(request) + request.path
    page = request.GET.get("page", "")
    if not noindex_by_params and page.isdigit() and int(page) > 1:
        url += f"?page={page}"
    return url


# ---------- ساخت ----------

def build(request, context, obj=None, *, title=None, description=None, image=None, og_type=None,
          noindex=False, raw_title=False, breadcrumbs=None, home=False):
    site = context.get("SITE") or {}
    store = getattr(request, "store", None)
    config = getattr(store, "config", None) if store is not None else None
    theme_settings = context.get("THEME_SETTINGS")
    site_name, tagline = site.get("name", ""), site.get("tagline", "")
    kind = _kind(obj)

    if obj is not None and getattr(obj, "meta_title", ""):
        final_title = obj.meta_title
    elif title:
        final_title = title if raw_title else f"{title} | {site_name}"
    else:
        final_title = _default_title(obj, kind, site_name, tagline)

    store_description = getattr(config, "meta_description", "") or tagline
    final_description = clean_text(
        (getattr(obj, "meta_description", "") if obj is not None else "")
        or description or _object_description(obj, kind) or store_description
    )

    noindex_by_params = any(v for k, v in request.GET.items() if k not in INDEXABLE_PARAMS)
    robots = ROBOTS_NOINDEX if _is_noindex(request, obj, noindex) else ROBOTS_INDEX
    canonical = _canonical(request, noindex_by_params)
    logo = absolute(request, _image_url(getattr(theme_settings, "logo", None)))
    img = image or _object_image(obj, kind) or _image_url(getattr(config, "og_image", None))

    seo = Seo(
        title=clean_text(final_title, 0),
        description=final_description,
        canonical=canonical,
        robots=robots,
        og_type=og_type or {"catalog.product": "product", "blog.post": "article"}.get(kind, "website"),
        image=absolute(request, img),
        image_alt=getattr(obj, "name", None) or getattr(obj, "title", None) or site_name,
        site_name=site_name,
        twitter=("@" + config.twitter_handle.lstrip("@")) if getattr(config, "twitter_handle", "") else "",
    )
    if not seo.indexable:
        return seo  # داده ساختاریافته فقط برای صفحه‌های قابل index

    to_abs = lambda url: absolute(request, url)  # noqa: E731
    home_url = to_abs(reverse("pages:home"))
    if home:
        seo.verification = {
            "google-site-verification": getattr(config, "google_site_verification", ""),
            "msvalidate.01": getattr(config, "bing_site_verification", ""),
        }
        seo.jsonld += [
            jsonld.website(site, url=home_url, absolute=to_abs),
            jsonld.organization(site, url=home_url, logo=logo, description=store_description),
        ]
    if kind == "catalog.product":
        gallery = [absolute(request, _image_url(f)) for f in context.get("gallery") or []] or [seo.image]
        seo.jsonld.append(jsonld.product(
            obj, url=canonical, images=[g for g in gallery if g], description=clean_text(obj.short_description, 500),
            currency_code=getattr(config, "currency_code", "IRR"), currency_factor=getattr(config, "currency_factor", 10),
        ))
        breadcrumbs = breadcrumbs or [("خانه", reverse("pages:home")), ("عطرها", reverse("catalog:shop")),
                                      (obj.name, obj.get_absolute_url())]
    elif kind == "blog.post":
        seo.jsonld.append(jsonld.article(obj, url=canonical, image=seo.image, description=final_description,
                                         site_name=site_name, logo=logo))
        breadcrumbs = breadcrumbs or [("خانه", reverse("pages:home")), ("مجله", reverse("blog:list")),
                                      (obj.title, obj.get_absolute_url())]
    elif kind == "catalog.collection":
        breadcrumbs = breadcrumbs or [("خانه", reverse("pages:home")), ("کالکشن‌ها", reverse("catalog:collections")),
                                      (obj.name, obj.get_absolute_url())]
    elif kind == "catalog.category":
        trail = [(c.name, c.get_absolute_url()) for c in obj.ancestors()] if hasattr(obj, "ancestors") else []
        breadcrumbs = breadcrumbs or [("خانه", reverse("pages:home")), ("فروشگاه", reverse("catalog:shop")),
                                      *trail, (obj.name, obj.get_absolute_url())]
    if breadcrumbs:
        seo.jsonld.append(jsonld.breadcrumbs(breadcrumbs, to_abs))
    seo.jsonld = [jsonld.json_dumps_safe(block) for block in seo.jsonld]
    return seo
