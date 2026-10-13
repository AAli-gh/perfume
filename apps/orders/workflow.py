"""چرخه وضعیت سفارش (State Machine).

همه تغییر وضعیت‌ها — از پنل، درگاه پرداخت یا Task — از transition() عبور می‌کنند تا:
- فقط تغییرهای مجاز انجام شوند؛
- اثرهای جانبی (آزادسازی موجودی، زمان پرداخت) دقیقاً یک بار اجرا شوند؛
- تاریخچه هر تغییر ثبت شود.
"""

from django.db import transaction
from django.utils import timezone

from apps.catalog import inventory
from apps.discounts import credits, referrals

from . import giftcards
from .models import Order, OrderStatusHistory
from .signals import order_status_changed

S = Order.Status

TRANSITIONS = {
    S.PENDING: {S.PAID, S.PROCESSING, S.CANCELLED},
    S.PAID: {S.PROCESSING, S.CANCELLED},
    S.PROCESSING: {S.SHIPPED, S.CANCELLED},
    S.SHIPPED: {S.DELIVERED},
    S.DELIVERED: set(),
    S.CANCELLED: set(),
}


class InvalidTransition(Exception):
    pass


def allowed_transitions(status):
    return TRANSITIONS.get(status, set())


def can_transition(from_status, to_status):
    return from_status == to_status or to_status in allowed_transitions(from_status)


def stock_lines(order):
    return [inventory.StockLine(i.variant_id, i.quantity) for i in order.items.exclude(variant=None)]


@transaction.atomic
def transition(order, to_status, *, by=None, note=""):
    locked = Order.objects.select_for_update().get(pk=order.pk)
    current = locked.status
    if current == to_status:
        return locked
    if to_status not in allowed_transitions(current):
        raise InvalidTransition(f"تغییر وضعیت از «{locked.get_status_display()}» به «{S(to_status).label}» مجاز نیست.")

    locked.status = to_status
    fields = ["status"]
    if to_status == S.PAID and locked.paid_at is None:
        locked.paid_at = timezone.now()
        fields.append("paid_at")
    if to_status == S.SHIPPED and locked.shipped_at is None:
        locked.shipped_at = timezone.now()
        fields.append("shipped_at")
    if to_status == S.CANCELLED and not locked.inventory_released:
        inventory.release(stock_lines(locked), locked.number, by, note or "لغو سفارش")
        locked.inventory_released = True
        fields.append("inventory_released")
    if to_status == S.CANCELLED:
        credits.restore_for_order(locked)  # کارت هدیه و امتیاز خرج‌شده برمی‌گردد
        giftcards.void_purchased(locked)
    paid_now = to_status == S.PAID or (to_status == S.DELIVERED and locked.payment_method == Order.PaymentMethod.COD)
    if paid_now and not locked.gift_cards_issued:
        giftcards.issue_purchased(locked)
        locked.gift_cards_issued = True
        fields.append("gift_cards_issued")
    if to_status == S.DELIVERED:
        transaction.on_commit(lambda: credits.earn_for_order(locked))
        transaction.on_commit(lambda: referrals.reward_for_order(locked))
    locked.save(update_fields=fields)
    OrderStatusHistory.objects.create(order=locked, from_status=current, to_status=to_status, changed_by=by, note=note)
    transaction.on_commit(lambda: order_status_changed.send(
        sender=Order, order=locked, from_status=current, to_status=to_status))

    for f in fields:  # همگام‌سازی نمونه‌ای که فراخوان در دست دارد
        setattr(order, f, getattr(locked, f))
    return locked


def expire_unpaid_orders(now=None):
    """لغو سفارش‌های آنلاینِ پرداخت‌نشده‌ای که مهلت پرداختشان گذشته؛ خروجی: تعداد."""
    now = now or timezone.now()
    expired = Order.objects.filter(status=S.PENDING, paid_at=None, reserved_until__lt=now).values_list("pk", flat=True)
    count = 0
    for pk in expired:
        order = Order.objects.get(pk=pk)
        try:
            transition(order, S.CANCELLED, note="انقضای مهلت پرداخت")
            count += 1
        except InvalidTransition:
            continue  # در فاصله کوئری تا قفل، وضعیت عوض شده (مثلاً پرداخت شد)
    return count
