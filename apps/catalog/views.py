from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import selectors
from .forms import ReviewForm, ShopFilterForm
from .models import Collection, Product
from .services import submit_review

PER_PAGE = 8


def _render_partial_or_page(request, partial, page, context):
    if request.htmx and not request.htmx.boosted:
        return render(request, partial, context)
    return render(request, page, context)


def shop(request):
    brands = selectors.brands_with_counts()
    scents = selectors.scents_with_counts()
    form = ShopFilterForm(request.GET or None, brands=brands, scents=scents)
    lo, hi = selectors.price_bounds()

    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    collection = Collection.objects.filter(slug=data["collection"]).first() if data.get("collection") else None
    filters = selectors.ProductFilters(
        q=data.get("q", "").strip(),
        brands=data.get("brand", []),
        scents=data.get("scent", []),
        collection=collection,
        min_price=data.get("min_price"),
        max_price=data.get("max_price"),
        sort=data.get("sort", ""),
    )
    products = selectors.filter_products(filters, bounds=(lo, hi))
    if data.get("collection") and collection is None:
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
        "sort": filters.sort,
        "price_lo": lo,
        "price_hi": hi,
        "min_price": filters.min_price if filters.min_price is not None else lo,
        "max_price": filters.max_price if filters.max_price is not None else hi,
    }
    return _render_partial_or_page(request, "catalog/partials/results.html", "catalog/shop.html", context)


def collections(request):
    return render(request, "catalog/collections.html", {"collections": selectors.collections_with_counts()})


def product_detail(request, slug):
    try:
        product = selectors.product_detail(slug)
    except Product.DoesNotExist:
        raise Http404
    initial = {"name": request.user.display_name} if request.user.is_authenticated else {}
    return render(request, "catalog/product.html", {
        "product": product,
        "gallery": selectors.product_gallery(product),
        "variants": list(product.variants.all()),
        "reviews": product.reviews.filter(is_approved=True),
        "review_form": ReviewForm(initial=initial),
        "related": selectors.related_products(product),
    })


@require_POST
def review_create(request, slug):
    product = get_object_or_404(Product.objects.active(), slug=slug)
    form = ReviewForm(request.POST)
    submitted = form.is_valid()
    if submitted:
        submit_review(product, form, request.user)
        form = ReviewForm()
    context = {"product": product, "review_form": form, "submitted": submitted}
    if request.htmx:
        return render(request, "catalog/partials/review_form.html", context)
    if submitted:
        messages.success(request, "نظر شما ثبت شد و پس از تأیید نمایش داده می‌شود.")
    return redirect(product.get_absolute_url() + "#reviews")
