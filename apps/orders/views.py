from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.cart.cart import Cart, CartLine

from .forms import PROVINCES, CheckoutForm
from . import returns
from .models import Order, ReturnRequest
from .selectors import get_owned_order, remember_order
from .services import CouponUnavailable, OutOfStock, create_order
from apps.core.forms import en_digits
from apps.core.ratelimit import ratelimit


@ratelimit("checkout", "10/10m")
@require_POST
def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("cart:detail")

    form = CheckoutForm(request.POST, store=request.store, cart=cart)
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
    extra = [CartLine(box, 1)] if (box := form.chosen_gift_box()) else []
    return {"quote": cart.quote(method, province, extra), "shipping_label": method.name if method else "",
            "extra_lines": extra}


@require_POST
def quote(request):
    """HTMX: به‌روزرسانی خلاصه سفارش با تغییر استان یا روش ارسال."""
    cart = Cart(request)
    form = CheckoutForm(request.POST, store=request.store, cart=cart)
    context = {"cart": cart, "summary_id": "checkout-summary", **_quote_context(cart, form)}
    return render(request, "cart/partials/summary.html", context)


def detail(request, number):
    order = get_owned_order(request, number)
    can_return = returns.customer_can_request(order)
    return render(request, "orders/detail.html", {
        "order": order, "can_return": can_return, "returnable": returns.available(order) if can_return else {},
        "return_reasons": [c for c in ReturnRequest.Reason.choices if c[0] != ReturnRequest.Reason.OUT_OF_STOCK],
        "return_deadline": returns.return_deadline(order) if can_return else None,
        "return_requests": order.returns.prefetch_related("items__order_item"),
    })


def _quantities(order, data):
    out = {}
    for item in order.items.all():
        try:
            qty = int(en_digits(data.get(f"qty-{item.pk}", "0")) or 0)
        except ValueError:
            qty = 0
        if qty > 0:
            out[item] = qty
    return out


@require_POST
@ratelimit("return-request", "5/1h")
def request_return(request, number):
    """مشتری: درخواست مرجوعی برای سفارش ارسال‌شده (در مهلت مرجوعی فروشگاه)."""
    order = get_owned_order(request, number)
    if not returns.customer_can_request(order):
        messages.error(request, "برای این سفارش امکان ثبت درخواست مرجوعی نیست.")
        return redirect(order)
    reason = request.POST.get("reason", "")
    if reason not in dict(ReturnRequest.Reason.choices) or reason == ReturnRequest.Reason.OUT_OF_STOCK:
        messages.error(request, "علت مرجوعی را انتخاب کنید.")
        return redirect(order)
    try:
        returns.request_return(order, _quantities(order, request.POST), reason=reason,
                               description=request.POST.get("description", "").strip())
    except returns.ReturnError as exc:
        messages.error(request, str(exc))
        return redirect(order)
    messages.success(request, "درخواست مرجوعی ثبت شد؛ نتیجه بررسی با پیامک اطلاع داده می‌شود.")
    return redirect(order)
