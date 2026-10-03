from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from . import selectors
from .forms import ShopFilterForm
from .models import Category, Collection, Product

PER_PAGE = 8


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
    products = selectors.filter_products(store, filters, bounds=(lo, hi))
    if (data.get("collection") and collection is None) or (data.get("category") and category is None):
        products = products.none()
    page = Paginator(products, PER_PAGE).get_page(request.GET.get("page"))

    context = {
        "form": form,
        "page": page,
        "brands": brands,
        "scents": scents,
        "selected_brands": filters.brands,
        "selected_scents": filters.scents,
        "q": filters.q,
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
        raise Http404
    return render(request, "catalog/product.html", {
        "product": product,
        "gallery": selectors.product_gallery(product),
        "variants": list(product.variants.all()),
        "related": selectors.related_products(product),
    })
