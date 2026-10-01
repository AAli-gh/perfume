from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.cart.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .selectors import get_owned_order, remember_order
from .services import CouponUnavailable, OutOfStock, create_order


@require_POST
def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("cart:detail")

    form = CheckoutForm(request.POST, store=request.store)
    if not form.is_valid():
        return render(request, "cart/detail.html", {"cart": cart, "form": form, "form_error": True}, status=422)
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


def detail(request, number):
    return render(request, "orders/detail.html", {"order": get_owned_order(request, number)})
