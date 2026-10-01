import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.cart.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .payments import PaymentError, get_gateway
from .services import OutOfStock, create_order

log = logging.getLogger(__name__)
SESSION_ORDERS = "orders"


def _remember(request, order):
    numbers = request.session.get(SESSION_ORDERS, [])
    request.session[SESSION_ORDERS] = (numbers + [order.number])[-20:]


def _get_owned_order(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    owns = (
        number in request.session.get(SESSION_ORDERS, [])
        or (request.user.is_authenticated and order.user_id == request.user.pk)
        or request.user.is_staff
    )
    if not owns:
        raise Http404
    return order


@require_POST
def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("cart:detail")

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        return render(request, "cart/detail.html", {"cart": cart, "form": form, "form_error": True}, status=422)
    try:
        order = create_order(cart, form, request.user)
    except OutOfStock as exc:
        messages.error(request, "موجودی این کالاها کافی نیست: " + "، ".join(exc.names))
        return redirect("cart:detail")

    cart.clear()
    _remember(request, order)
    if order.payment_method == Order.PaymentMethod.ONLINE:
        return redirect("orders:pay", number=order.number)
    messages.success(request, "سفارش شما با موفقیت ثبت شد.")
    return redirect(order)


def detail(request, number):
    return render(request, "orders/detail.html", {"order": _get_owned_order(request, number)})


def pay(request, number):
    order = _get_owned_order(request, number)
    if order.is_paid or order.status != Order.Status.PENDING:
        return redirect(order)
    try:
        gateway = get_gateway()
        authority, url = gateway.request(order, request.build_absolute_uri(reverse("orders:callback")))
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect(order)
    order.payment_authority = authority
    order.payment_method = Order.PaymentMethod.ONLINE
    order.save(update_fields=["payment_authority", "payment_method"])
    return redirect(url)


def callback(request):
    authority = request.GET.get("Authority", "")
    status = request.GET.get("Status", "")
    if not authority:
        raise Http404
    order = get_object_or_404(Order, payment_authority=authority)
    if order.is_paid:
        return redirect(order)
    if status != "OK":
        messages.error(request, "پرداخت انجام نشد یا توسط شما لغو شد. می‌توانید دوباره تلاش کنید.")
        return redirect(order)
    try:
        result = get_gateway().verify(order, authority)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect(order)
    if not result.ok:
        messages.error(request, result.message)
        return redirect(order)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.is_paid:
            order.status = Order.Status.PAID
            order.paid_at = timezone.now()
            order.payment_ref_id = result.ref_id
            order.save(update_fields=["status", "paid_at", "payment_ref_id"])
    messages.success(request, "پرداخت با موفقیت انجام شد. از خرید شما سپاسگزاریم!")
    return redirect(order)


def fake_gateway(request, authority):
    """صفحه درگاه آزمایشی (فقط DEBUG و بدون مرچنت زرین‌پال)."""
    if not settings.DEBUG or settings.ZARINPAL_MERCHANT_ID:
        raise Http404
    order = get_object_or_404(Order, payment_authority=authority)
    callback = reverse("orders:callback")
    return render(request, "orders/fake_gateway.html", {"order": order, "callback": callback, "authority": authority})
