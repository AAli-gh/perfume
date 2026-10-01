"""Selectorهای کاتالوگ: همه کوئری‌های خواندنی محصولات در یک‌جا.

Viewها و Sectionهای صفحه (در آینده) فقط از این توابع داده می‌گیرند،
تا منطق فیلتر/مرتب‌سازی به قالب یا Theme خاصی وابسته نباشد.
"""

from dataclasses import dataclass, field

from django.db.models import Count, F, Max, Min, Q

from .models import Brand, Collection, Product, ProductVariant, ScentFamily

PRICE_STEP = 100_000

SORT_ORDER = {
    "": ["-is_featured", "-created_at"],
    "rating": [F("rating_avg").desc(nulls_last=True), "-review_count"],
    "price": ["min_price"],
    "-price": ["-min_price"],
    "new": ["-created_at"],
}


def listable_products(store):
    """محصولات فعال فروشگاه همراه با آمار (کمترین قیمت، امتیاز، تعداد نظر) و روابط لازم برای کارت محصول."""
    return (
        Product.objects.for_store(store)
        .active()
        .with_stats()
        .select_related("brand", "scent")
        .prefetch_related("variants")
    )


def price_bounds(store):
    """کمترین و بیشترین قیمت حجم‌های فعال فروشگاه، گردشده به PRICE_STEP."""
    agg = ProductVariant.objects.filter(product__store=store, product__is_active=True).aggregate(lo=Min("price"), hi=Max("price"))
    lo = (agg["lo"] or 0) // PRICE_STEP * PRICE_STEP
    hi = -(-(agg["hi"] or 0) // PRICE_STEP) * PRICE_STEP
    return lo, hi


# توجه: Django در کوئری‌های GROUP BY (annotate + Count) ترتیب پیش‌فرض Meta.ordering را اعمال نمی‌کند؛
# پس ترتیب را صریح می‌نویسیم تا خروجی قطعی باشد.

def brands_with_counts(store):
    return (
        Brand.objects.for_store(store)
        .annotate(n=Count("products", filter=Q(products__is_active=True)))
        .filter(n__gt=0)
        .order_by(*Brand._meta.ordering)
    )


def scents_with_counts(store):
    return (
        ScentFamily.objects.for_store(store)
        .annotate(n=Count("products", filter=Q(products__is_active=True)))
        .filter(n__gt=0)
        .order_by(*ScentFamily._meta.ordering)
    )


def collections_with_counts(store):
    return (
        Collection.objects.for_store(store)
        .annotate(n=Count("products", filter=Q(products__is_active=True)))
        .order_by(*Collection._meta.ordering)
    )


@dataclass
class ProductFilters:
    q: str = ""
    brands: list = field(default_factory=list)
    scents: list = field(default_factory=list)
    collection: Collection | None = None
    min_price: int | None = None
    max_price: int | None = None
    sort: str = ""


def filter_products(store, filters: ProductFilters, bounds=None):
    """اعمال فیلترهای فروشگاه روی محصولات قابل نمایش."""
    lo, hi = bounds or price_bounds(store)
    products = listable_products(store)
    if filters.q:
        q = filters.q
        products = products.filter(
            Q(name__icontains=q) | Q(brand__name__icontains=q) | Q(scent__name__icontains=q)
            | Q(short_description__icontains=q) | Q(notes_top__icontains=q)
            | Q(notes_middle__icontains=q) | Q(notes_base__icontains=q)
        )
    if filters.brands:
        products = products.filter(brand__slug__in=filters.brands)
    if filters.scents:
        products = products.filter(scent__slug__in=filters.scents)
    if filters.collection is not None:
        products = products.filter(collection=filters.collection)
    if filters.min_price is not None and filters.min_price > lo:
        products = products.filter(min_price__gte=filters.min_price)
    if filters.max_price is not None and filters.max_price < hi:
        products = products.filter(min_price__lte=filters.max_price)
    return products.order_by(*SORT_ORDER.get(filters.sort, SORT_ORDER[""]))


def best_sellers(store, limit=8):
    return listable_products(store).order_by(F("rating_avg").desc(nulls_last=True), "-review_count")[:limit]


def product_detail(store, slug):
    """محصول فعال فروشگاه با گالری؛ اگر وجود نداشته باشد Product.DoesNotExist."""
    return listable_products(store).prefetch_related("images").get(slug=slug)


def related_products(product, limit=8):
    return (
        listable_products(product.store_id)
        .exclude(pk=product.pk)
        .filter(Q(collection=product.collection) | Q(scent=product.scent))
        .order_by(F("rating_avg").desc(nulls_last=True))[:limit]
    )


def product_gallery(product):
    return [product.image] + [img.image for img in product.images.all()]
