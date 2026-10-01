from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.orders.selectors import get_owned_order

from .gateways import PaymentError
from .models import Payment
from .services import TEST_GATEWAY, handle_callback, start_payment


def start(request, number):
    order = get_owned_order(request, number)
    try:
        url = start_payment(order, lambda code: request.build_absolute_uri(reverse("payments:callback", args=[code])))
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect(order)
    return redirect(url)


def callback(request, gateway):
    params = request.POST if request.method == "POST" else request.GET
    try:
        payment = handle_callback(gateway, params, request.store)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("pages:home")
    if payment.status == Payment.Status.SUCCEEDED:
        messages.success(request, "پرداخت با موفقیت انجام شد. از خرید شما سپاسگزاریم!")
    elif payment.status == Payment.Status.CANCELLED:
        messages.error(request, "پرداخت انجام نشد یا توسط شما لغو شد. می‌توانید دوباره تلاش کنید.")
    else:
        messages.error(request, payment.message or "پرداخت ناموفق بود.")
    return redirect(payment.order)


def legacy_zarinpal_callback(request):
    """آدرس بازگشت قبلی (/orders/payment/callback/) برای تراکنش‌هایی که قبل از به‌روزرسانی شروع شده‌اند."""
    return callback(request, "zarinpal")


def test_gateway(request, authority):
    if not getattr(settings, "PAYMENT_TEST_GATEWAY_ENABLED", False):
        raise Http404
    payment = get_object_or_404(Payment, gateway=TEST_GATEWAY, authority=authority, order__store=request.store)
    return render(request, "payments/test_gateway.html", {
        "order": payment.order, "authority": authority, "callback": reverse("payments:callback", args=[TEST_GATEWAY]),
    })
