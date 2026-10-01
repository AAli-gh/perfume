"""سرویس پرداخت: شروع تراکنش و پردازش بازگشت از درگاه.

قواعد مهم:
- پردازش بازگشت اتمیک و تکرارپذیر (idempotent) است: بازگشت تکراری از درگاه پرداخت را دوبار ثبت نمی‌کند.
- اگر سفارش دیگر قابل پرداخت نباشد (مثلاً مهلتش تمام شده و موجودی آزاد شده)، تراکنش verify نمی‌شود؛
  در زرین‌پال تراکنشِ verify نشده به‌طور خودکار به حساب مشتری برمی‌گردد.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.workflow import InvalidTransition, transition

from .gateways import PaymentError, get_gateway_class
from .models import GatewayAccount, Payment

log = logging.getLogger(__name__)
TEST_GATEWAY = "test"


def _test_gateway_enabled():
    return bool(getattr(settings, "PAYMENT_TEST_GATEWAY_ENABLED", False))


def active_accounts(store):
    return [a for a in GatewayAccount.objects.for_store(store).filter(is_active=True) if a.gateway != TEST_GATEWAY]


def online_payment_available(store):
    return bool(active_accounts(store)) or _test_gateway_enabled()


def gateway_for(store, code=None):
    """(درگاه, حساب) برای فروشگاه؛ اگر code ندهید، اولین درگاه فعال."""
    accounts = active_accounts(store)
    if code and code != TEST_GATEWAY:
        accounts = [a for a in accounts if a.gateway == code]
    if accounts and code != TEST_GATEWAY:
        account = accounts[0]
        return get_gateway_class(account.gateway)(account), account
    if _test_gateway_enabled() and code in (None, TEST_GATEWAY):
        return get_gateway_class(TEST_GATEWAY)(None), None
    raise PaymentError("درگاه پرداخت برای این فروشگاه فعال نیست.")


def _ensure_payable(order):
    if order.status != Order.Status.PENDING or order.is_paid:
        raise PaymentError("این سفارش دیگر قابل پرداخت نیست.")
    if order.reserved_until and order.reserved_until < timezone.now():
        try:
            transition(order, Order.Status.CANCELLED, note="انقضای مهلت پرداخت")
        except InvalidTransition:
            pass
        raise PaymentError("مهلت پرداخت این سفارش به پایان رسیده و سفارش لغو شد.")


def start_payment(order, build_callback_url):
    """ایجاد Payment و تراکنش درگاه؛ خروجی: آدرس انتقال کاربر به درگاه."""
    _ensure_payable(order)
    gateway, _account = gateway_for(order.store)
    payment = Payment.objects.create(order=order, gateway=gateway.code, amount=order.total)
    try:
        result = gateway.initiate(payment, build_callback_url(gateway.code))
    except PaymentError as exc:
        payment.status, payment.message = Payment.Status.FAILED, str(exc)
        payment.save(update_fields=["status", "message", "updated_at"])
        raise
    payment.authority, payment.status = result.authority, Payment.Status.PENDING
    payment.raw = {**payment.raw, **result.raw}
    payment.save(update_fields=["authority", "status", "raw", "updated_at"])
    return result.redirect_url


@transaction.atomic
def handle_callback(gateway_code, params, store):
    """پردازش بازگشت از درگاه؛ خروجی: Payment به‌روزشده."""
    gateway_cls = get_gateway_class(gateway_code)
    data = gateway_cls(None).parse_callback(params)
    payment = (
        Payment.objects.select_for_update()
        .select_related("order")
        .filter(gateway=gateway_code, authority=data.authority, order__store=store)
        .first()
    )
    if payment is None or not data.authority:
        raise PaymentError("تراکنش پیدا نشد.")
    if payment.status in (Payment.Status.SUCCEEDED, Payment.Status.FAILED, Payment.Status.CANCELLED, Payment.Status.EXPIRED):
        return payment  # بازگشت تکراری

    payment.raw = {**payment.raw, "callback": data.raw}
    order = payment.order
    if not data.success:
        payment.status, payment.message = Payment.Status.CANCELLED, "پرداخت توسط کاربر لغو شد یا ناموفق بود."
    elif order.status != Order.Status.PENDING or order.is_paid:
        payment.status = Payment.Status.EXPIRED
        payment.message = "سفارش دیگر قابل پرداخت نبود؛ تراکنش تأیید نشد و مبلغ توسط درگاه بازگردانده می‌شود."
        log.warning("Payment %s for non-payable order %s left unverified", payment.pk, order.number)
    else:
        account = None
        if gateway_code != TEST_GATEWAY:
            account = GatewayAccount.objects.for_store(store).filter(gateway=gateway_code).first()
            if account is None:
                raise PaymentError("درگاه پرداخت برای این فروشگاه فعال نیست.")
        elif not _test_gateway_enabled():
            raise PaymentError("درگاه آزمایشی غیرفعال است.")
        result = gateway_cls(account).verify(payment, data)
        payment.raw = {**payment.raw, **result.raw}
        if result.ok:
            payment.status, payment.ref_id, payment.card_pan = Payment.Status.SUCCEEDED, result.ref_id, result.card_pan
            payment.verified_at = timezone.now()
            transition(order, Order.Status.PAID, note=f"پرداخت آنلاین — کد پیگیری {result.ref_id}")
        else:
            payment.status, payment.message = Payment.Status.FAILED, result.message
    payment.save()
    return payment


def successful_payment(order):
    return order.payments.filter(status=Payment.Status.SUCCEEDED).order_by("-verified_at").first()
