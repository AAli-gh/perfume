from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.core.ratelimit import ratelimit

from . import samples, search_log, selectors, services
from .history import remember_view
from .recommend import similar_products
from .forms import BackInStockForm, ShopFilterForm
from .models import Category, Collection, Product

PER_PAGE = 8
SUGGEST_LIMIT = 5


def _render_partial_or_page(request, partial, page, context):
    if request.htmx and not request.htmx.boosted:
        return render(request, partial, context)
    return render(request, page, context)


def shop(request, *, landing=None):
    """فروشگاه با فیلترها. landing: کالکشن یا دسته‌ای که صفحه اختصاصی دارد (آدرس تمیز برای سئو)."""
    store = request.store
    brands = selectors.brands_with_counts(store)
    scents = selectors.scents_with_counts(store)
    form = ShopFilterForm(request.GET or None, brands=brands, scents=scents)
    lo, hi = selectors.price_bounds(store)

    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    collection = landing if isinstance(landing, Collection) else None
    category = landing if isinstance(landing, Category) else None
    if collection is None and data.get("collection"):
        collection = Collection.objects.for_store(store).filter(slug=data["collection"]).first()
    if category is None and data.get("category"):
        category = Category.objects.for_store(store).filter(slug=data["category"], is_active=True).first()
    filters = selectors.ProductFilters(
        q=data.get("q", "").strip(),
        brands=data.get("brand", []),
        scents=data.get("scent", []),
        collection=collection,
        categories=[category.slug] if category else [],
        min_price=data.get("min_price"),
        max_price=data.get("max_price"),
        sort=data.get("sort", ""),
    )
    search = selectors.search_shop(store, filters, bounds=(lo, hi))
    products = search.products
    if (data.get("collection") and collection is None) or (data.get("category") and category is None):
        products = products.none()
    page = Paginator(products, PER_PAGE).get_page(request.GET.get("page"))
    if filters.q and page.number == 1:
        search_log.record_search(request, filters.q, search, page.paginator.count)

    context = {
        "form": form,
        "page": page,
        "brands": brands,
        "scents": scents,
        "selected_brands": filters.brands,
        "selected_scents": filters.scents,
        "q": filters.q,
        **_search_context(search),
        "collection": collection,
        "category": category,
        "landing": landing,
        "sort": filters.sort,
        "price_lo": lo,
        "price_hi": hi,
        "min_price": filters.min_price if filters.min_price is not None else lo,
        "max_price": filters.max_price if filters.max_price is not None else hi,
    }
    return _render_partial_or_page(request, "catalog/partials/results.html", "catalog/shop.html", context)


def _search_context(search):
    """برداشت جستجوی هوشمند برای قالب: برچسب‌ها با پیوند حذف، شرط‌های کنارگذاشته و کلمات نادیده."""
    parsed = search.parsed
    if parsed is None or not parsed.is_smart:
        return {"smart": None}
    chips = [{"label": c.label, "kind": c.kind, "negated": c.negated, "note": c.note,
              "relaxed": c in search.relaxed, "remove_q": parsed.without(c)} for c in parsed.criteria]
    return {"smart": {"chips": chips, "exact": search.exact, "relaxed": [c.label for c in search.relaxed],
                      "ignored": parsed.ignored}}


@ratelimit("search-suggest", "120/1m", methods=("GET",))
def search_suggest(request):
    """HTMX: پیش‌نمایش زنده جستجو در پنل جستجوی هدر (برداشت از عبارت + چند نتیجه اول)."""
    q = request.GET.get("q", "").strip()[:200]
    if not q:
        return render(request, "catalog/partials/search_suggest.html", {"q": ""})
    search = selectors.search_shop(request.store, selectors.ProductFilters(q=q))
    products = list(search.products[:SUGGEST_LIMIT + 1])
    context = {"q": q, "products": products[:SUGGEST_LIMIT], "more": len(products) > SUGGEST_LIMIT,
               **_search_context(search)}
    return render(request, "catalog/partials/search_suggest.html", context)


def collection_detail(request, slug):
    collection = Collection.objects.for_store(request.store).filter(slug=slug).first()
    if collection is None:
        raise Http404
    return shop(request, landing=collection)


def category_detail(request, slug):
    category = Category.objects.for_store(request.store).filter(slug=slug, is_active=True).first()
    if category is None:
        raise Http404
    return shop(request, landing=category)


def collections(request):
    return render(request, "catalog/collections.html", {"collections": selectors.collections_with_counts(request.store)})


def product_detail(request, slug):
    try:
        product = selectors.product_detail(request.store, slug)
    except Product.DoesNotExist:
        raise Http404 from None
    remember_view(request, product)
    variants = sorted(product.variants.all(), key=lambda v: (v.is_decant, v.size_ml))  # شیشه‌ها اول، بعد نمونه‌ها
    return render(request, "catalog/product.html", {
        "product": product,
        "notify_form": _notify_form(request, variants),
        "gallery": selectors.product_gallery(product),
        "variants": variants,
        "related": (selectors.related_products(product) if product.is_accessory
                    else similar_products(product) or selectors.related_products(product)),
        "gift_boxes": [] if product.is_accessory else selectors.gift_boxes(request.store)[:4],
        "sample_boxes": [] if product.is_accessory else selectors.sample_boxes(request.store)[:3],
        "sample_choices": (samples.sample_choices(request.store, product.default_variant.size_ml)
                           if product.is_sample_box and product.default_variant else []),
    })


def _notify_form(request, variants, data=None):
    sold_out = [v for v in variants if v.stock <= 0]
    if not sold_out:
        return None
    phone = getattr(request.user, "phone", "") if request.user.is_authenticated else ""
    return BackInStockForm(data, variants=sold_out, initial={"phone": phone})


@require_POST
@ratelimit("back-in-stock", "10/10m")
def notify_me(request, slug):
    """HTMX: ثبت «موجود شد خبرم کن» برای یک حجم ناموجود."""
    try:
        product = selectors.product_detail(request.store, slug)
    except Product.DoesNotExist:
        raise Http404 from None
    form = _notify_form(request, list(product.variants.all()), request.POST)
    done = False
    if form is not None and form.is_valid():
        services.request_back_in_stock(form.cleaned_data["variant"], form.cleaned_data["phone"], request.user)
        done = True
    return render(request, "catalog/partials/notify_me.html", {"product": product, "notify_form": form, "done": done})


def samples_page(request):
    """نمونه و باکس تست: باکس‌های تست و عطرهایی که دکانت دارند."""
    return render(request, "catalog/samples.html", {
        "boxes": selectors.sample_boxes(request.store),
        "perfumes": selectors.with_decants(request.store),
    })


def gift_boxes(request):
    return render(request, "catalog/gift_boxes.html", {"boxes": selectors.gift_boxes(request.store),
                                                       "cards": selectors.gift_cards(request.store)})
