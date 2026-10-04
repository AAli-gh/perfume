from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.cart.cart import Cart

from .forms import PROVINCES, CheckoutForm
from .models import Order
from .selectors import get_owned_order, remember_order
from .services import CouponUnavailable, OutOfStock, create_order
from apps.core.ratelimit import ratelimit


@ratelimit("checkout", "10/10m")
@require_POST
def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("cart:detail")

    form = CheckoutForm(request.POST, store=request.store)
    if not form.is_valid():
        context = {"cart": cart, "form": form, "form_error": True, **_quote_context(cart, form)}
        return render(request, "cart/detail.html", context, status=422)
    try:
        order = create_order(cart, form, request.user)
    except OutOfStock as exc:
        messages.error(request, "موجودی این کالاها کافی نیست: " + "، ".join(exc.names))
        return redirect("cart:detail")
    except CouponUnavailable as exc:
        cart.remove_coupon()
        messages.error(request, f"{exc} سبد خرید بدون کد تخفیف به‌روز شد؛ لطفاً مبلغ را بررسی و دوباره ثبت کنید.")
        return redirect("cart:detail")

    cart.clear()
    remember_order(request, order)
    if order.payment_method == Order.PaymentMethod.ONLINE:
        return redirect("payments:start", number=order.number)
    messages.success(request, "سفارش شما با موفقیت ثبت شد.")
    return redirect(order)


def _quote_context(cart, form):
    """قیمت سبد با روش ارسال و استان انتخاب‌شده در فرم تسویه (حتی وقتی بقیه فرم هنوز ناقص است)."""
    methods = {str(m.pk): m for m in getattr(form, "shipping_methods", [])}
    method = methods.get(form.data.get("shipping_method", "")) or next(iter(methods.values()), None)
    province = form.data.get("province", "")
    if province not in PROVINCES:
        province = ""
    if method is None:
        return {}
    return {"quote": cart.quote(method, province), "shipping_label": method.name}


@require_POST
def quote(request):
    """HTMX: به‌روزرسانی خلاصه سفارش با تغییر استان یا روش ارسال."""
    cart = Cart(request)
    form = CheckoutForm(request.POST, store=request.store)
    context = {"cart": cart, "summary_id": "checkout-summary", **_quote_context(cart, form)}
    return render(request, "cart/partials/summary.html", context)


def detail(request, number):
    return render(request, "orders/detail.html", {"order": get_owned_order(request, number)})
