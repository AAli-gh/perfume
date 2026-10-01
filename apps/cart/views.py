from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import ProductVariant
from apps.core.forms import en_digits

from .cart import Cart
from .services import apply_coupon_code


def _qty(value, default=1):
    try:
        return int(en_digits(str(value)))
    except (TypeError, ValueError):
        return default


def _cart_area(request, cart, **extra):
    """پاسخ HTMX: بخش سبد + خلاصه سفارش و شمارنده هدر (out-of-band)."""
    return render(request, "cart/partials/cart_area.html", {"cart": cart, **extra})


def detail(request):
    return render(request, "cart/detail.html", {"cart": Cart(request)})


@require_POST
def add(request):
    cart = Cart(request)
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"), pk=request.POST.get("variant"), product__is_active=True
    )
    ok = variant.stock > 0
    if ok:
        cart.add(variant, max(1, _qty(request.POST.get("quantity"))))
    if request.htmx:
        return render(request, "cart/partials/added.html", {"variant": variant, "ok": ok, "cart": cart})
    if ok:
        messages.success(request, f"«{variant.product.name}» به سبد خرید اضافه شد.")
    else:
        messages.error(request, "این محصول در حال حاضر موجود نیست.")
    return redirect("cart:detail")


@require_POST
def update(request, variant_id):
    cart = Cart(request)
    variant = get_object_or_404(ProductVariant, pk=variant_id)
    current = next((line.quantity for line in cart if line.variant.pk == variant.pk), 0)
    if "delta" in request.POST:
        qty = current + _qty(request.POST["delta"], 0)
    else:
        qty = _qty(request.POST.get("quantity"), current)
    if qty < 1:
        cart.remove(variant.pk)
    elif current:
        cart.set(variant, qty)
    if request.htmx:
        return _cart_area(request, cart)
    return redirect("cart:detail")


@require_POST
def remove(request, variant_id):
    cart = Cart(request)
    cart.remove(variant_id)
    if request.htmx:
        return _cart_area(request, cart)
    return redirect("cart:detail")


@require_POST
def apply_coupon(request):
    cart = Cart(request)
    result = apply_coupon_code(cart, request.POST.get("code", ""))
    if request.htmx:
        return _cart_area(request, cart, coupon_msg=result.message, coupon_ok=result.ok)
    (messages.success if result.ok else messages.error)(request, result.message)
    return redirect("cart:detail")


@require_POST
def remove_coupon(request):
    cart = Cart(request)
    cart.remove_coupon()
    if request.htmx:
        return _cart_area(request, cart)
    return redirect("cart:detail")
