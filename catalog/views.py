from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ReviewForm, ShopFilterForm
from .models import Brand, Collection, Product, ProductVariant, ScentFamily

PER_PAGE = 8
PRICE_STEP = 100_000

SORT_ORDER = {
    "": ["-is_featured", "-created_at"],
    "rating": [F("rating_avg").desc(nulls_last=True), "-review_count"],
    "price": ["min_price"],
    "-price": ["-min_price"],
    "new": ["-created_at"],
}


def product_queryset():
    return (
        Product.objects.active()
        .with_stats()
        .select_related("brand", "scent")
        .prefetch_related("variants")
    )


def price_bounds():
    agg = ProductVariant.objects.filter(product__is_active=True).aggregate(lo=Min("price"), hi=Max("price"))
    lo = (agg["lo"] or 0) // PRICE_STEP * PRICE_STEP
    hi = -(-(agg["hi"] or 0) // PRICE_STEP) * PRICE_STEP
    return lo, hi


def shop(request):
    active = Q(products__is_active=True)
    brands = Brand.objects.annotate(n=Count("products", filter=active)).filter(n__gt=0)
    scents = ScentFamily.objects.annotate(n=Count("products", filter=active)).filter(n__gt=0)
    form = ShopFilterForm(request.GET or None, brands=brands, scents=scents)
    lo, hi = price_bounds()

    products = product_queryset()
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    q = data.get("q", "").strip()
    collection = None

    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(brand__name__icontains=q) | Q(scent__name__icontains=q)
            | Q(short_description__icontains=q) | Q(notes_top__icontains=q)
            | Q(notes_middle__icontains=q) | Q(notes_base__icontains=q)
        )
    if data.get("brand"):
        products = products.filter(brand__slug__in=data["brand"])
    if data.get("scent"):
        products = products.filter(scent__slug__in=data["scent"])
    if data.get("collection"):
        collection = Collection.objects.filter(slug=data["collection"]).first()
        products = products.filter(collection=collection)
    min_price = data.get("min_price")
    max_price = data.get("max_price")
    if min_price is not None and min_price > lo:
        products = products.filter(min_price__gte=min_price)
    if max_price is not None and max_price < hi:
        products = products.filter(min_price__lte=max_price)

    products = products.order_by(*SORT_ORDER.get(data.get("sort", ""), SORT_ORDER[""]))
    page = Paginator(products, PER_PAGE).get_page(request.GET.get("page"))

    context = {
        "form": form,
        "page": page,
        "brands": brands,
        "scents": scents,
        "selected_brands": data.get("brand", []),
        "selected_scents": data.get("scent", []),
        "q": q,
        "collection": collection,
        "sort": data.get("sort", ""),
        "price_lo": lo,
        "price_hi": hi,
        "min_price": min_price if min_price is not None else lo,
        "max_price": max_price if max_price is not None else hi,
    }
    if request.htmx and not request.htmx.boosted:
        return render(request, "catalog/partials/results.html", context)
    return render(request, "catalog/shop.html", context)


def collections(request):
    items = Collection.objects.annotate(n=Count("products", filter=Q(products__is_active=True)))
    return render(request, "catalog/collections.html", {"collections": items})


def product_detail(request, slug):
    product = get_object_or_404(product_queryset().prefetch_related("images"), slug=slug)
    related = (
        product_queryset()
        .exclude(pk=product.pk)
        .filter(Q(collection=product.collection) | Q(scent=product.scent))
        .order_by(F("rating_avg").desc(nulls_last=True))[:8]
    )
    gallery = [product.image] + [img.image for img in product.images.all()]
    initial = {"name": request.user.display_name} if request.user.is_authenticated else {}
    return render(request, "catalog/product.html", {
        "product": product,
        "gallery": gallery,
        "variants": list(product.variants.all()),
        "reviews": product.reviews.filter(is_approved=True),
        "review_form": ReviewForm(initial=initial),
        "related": related,
    })


@require_POST
def review_create(request, slug):
    product = get_object_or_404(Product.objects.active(), slug=slug)
    form = ReviewForm(request.POST)
    submitted = False
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user if request.user.is_authenticated else None
        review.save()
        submitted = True
        form = ReviewForm()
    context = {"product": product, "review_form": form, "submitted": submitted}
    if request.htmx:
        return render(request, "catalog/partials/review_form.html", context)
    if submitted:
        messages.success(request, "نظر شما ثبت شد و پس از تأیید نمایش داده می‌شود.")
    return redirect(product.get_absolute_url() + "#reviews")
