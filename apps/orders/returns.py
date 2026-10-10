"""مرجوعی و بازپرداخت، و لغو بخشی از سفارش.

مرجوعی (پس از ارسال):  درخواست (مشتری یا کارمند) ← تأیید/رد ← دریافت کالا (برگشت به انبار) ← ثبت بازپرداخت
لغو بخشی (پیش از ارسال): کارمند اقلام را کم می‌کند ← همان لحظه برگشت به انبار و کاهش مبلغ سفارش؛
                        اگر سفارش پرداخت شده بود، مبلغ بازپرداخت در انتظار ثبت می‌ماند.

مبلغ بازپرداخت هر قلم = قیمت × تعداد منهای سهم همان قلم از تخفیف سفارش (هزینه ارسال برنمی‌گردد).
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.catalog import inventory
from apps.catalog.models import StockMovement

from .models import Order, OrderItem, OrderStatusHistory, ReturnItem, ReturnRequest
from .signals import return_updated

R = ReturnRequest
S = Order.Status
CANCELLABLE = (S.PENDING, S.PAID, S.PROCESSING)
RETURNABLE = (S.SHIPPED, S.DELIVERED)


class ReturnError(Exception):
    pass


def refund_for(order, quantities):
    """quantities: {OrderItem: تعداد}؛ سهم تخفیف به نسبت مبلغ اقلام کم می‌شود."""
    gross = sum(item.unit_price * qty for item, qty in quantities.items())
    if not order.subtotal or not order.discount:
        return gross
    return max(gross - order.discount * gross // order.subtotal, 0)


def pending_quantities(order):
    """تعداد هر قلم که در درخواست‌های باز (هنوز دریافت/لغو نشده) است."""
    rows = (ReturnItem.objects.filter(request__order=order, request__status__in=[R.Status.REQUESTED, R.Status.APPROVED])
            .values("order_item").annotate(n=Sum("quantity")))
    return {r["order_item"]: r["n"] for r in rows}


def available(order):
    """{OrderItem: حداکثر تعداد قابل مرجوعی/لغو}."""
    pending = pending_quantities(order)
    return {item: item.returnable_quantity - pending.get(item.pk, 0) for item in order.items.all()
            if item.returnable_quantity - pending.get(item.pk, 0) > 0}


def return_deadline(order):
    days = getattr(getattr(order.store, "config", None), "return_days", 7)
    start = order.shipped_at or order.created_at
    return start + timedelta(days=days) if days else None


def customer_can_request(order, now=None):
    deadline = return_deadline(order)
    return (order.status in RETURNABLE and deadline is not None and (now or timezone.now()) <= deadline
            and bool(available(order)) and not order.returns.filter(status=R.Status.REQUESTED).exists())


def _validated(order, quantities):
    allowed = available(order)
    clean = {}
    for item, qty in quantities.items():
        if qty <= 0:
            continue
        if item not in allowed or qty > allowed[item]:
            raise ReturnError(f"تعداد «{item.product_name}» بیشتر از مقدار قابل مرجوعی است.")
        clean[item] = qty
    if not clean:
        raise ReturnError("دست‌کم یک کالا و تعداد آن را انتخاب کنید.")
    return clean


def _notify(request):
    transaction.on_commit(lambda: return_updated.send(sender=ReturnRequest, request=request))


@transaction.atomic
def request_return(order, quantities, *, reason, description="", by_customer=True, user=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in RETURNABLE:
        raise ReturnError("مرجوعی فقط برای سفارش ارسال‌شده یا تحویل‌شده ممکن است.")
    clean = _validated(order, quantities)
    req = ReturnRequest.objects.create(order=order, kind=R.Kind.RETURN, reason=reason, description=description[:1000],
                                       by_customer=by_customer, refund_amount=refund_for(order, clean),
                                       handled_by=None if by_customer else user)
    ReturnItem.objects.bulk_create([ReturnItem(request=req, order_item=item, quantity=qty) for item, qty in clean.items()])
    _notify(req)
    return req


def _set_status(req, status, user, note=""):
    req.status, req.handled_by = status, user
    if note:
        req.staff_note = (req.staff_note + "\n" + note).strip()
    req.save()
    _notify(req)
    return req


@transaction.atomic
def approve(req, user=None, note=""):
    req = ReturnRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != R.Status.REQUESTED:
        raise ReturnError("فقط درخواست در انتظار بررسی تأیید می‌شود.")
    return _set_status(req, R.Status.APPROVED, user, note)


@transaction.atomic
def reject(req, user=None, note=""):
    req = ReturnRequest.objects.select_for_update().get(pk=req.pk)
    if req.status not in (R.Status.REQUESTED, R.Status.APPROVED):
        raise ReturnError("این درخواست قابل رد نیست.")
    return _set_status(req, R.Status.REJECTED, user, note)


def _restock(req, user, note):
    lines = [inventory.StockLine(ri.order_item.variant_id, ri.quantity)
             for ri in req.items.select_related("order_item") if ri.order_item.variant_id]
    reason = StockMovement.Reason.RETURNED if req.kind == R.Kind.RETURN else StockMovement.Reason.RELEASED
    inventory.restock(lines, req.order.number, user, note, reason=reason)
    _mark_returned(req)
    req.restocked = True


def _mark_returned(req):
    for ri in req.items.all():
        OrderItem.objects.filter(pk=ri.order_item_id).update(returned_quantity=F("returned_quantity") + ri.quantity)


@transaction.atomic
def receive(req, user=None, *, restock=True, note=""):
    """کالای مرجوعی رسید؛ با restock=False (مثلاً شکسته) به انبار برنمی‌گردد."""
    req = ReturnRequest.objects.select_for_update().get(pk=req.pk)
    if req.status not in (R.Status.REQUESTED, R.Status.APPROVED):
        raise ReturnError("این درخواست در وضعیت دریافت کالا نیست.")
    if restock:
        _restock(req, user, note or "مرجوعی مشتری")
    else:
        _mark_returned(req)
    return _set_status(req, R.Status.RECEIVED, user, note)


@transaction.atomic
def refund(req, *, amount, method, reference="", user=None, note=""):
    req = ReturnRequest.objects.select_for_update().select_related("order").get(pk=req.pk)
    if req.status not in (R.Status.RECEIVED, R.Status.APPROVED):
        raise ReturnError("بازپرداخت بعد از تأیید یا دریافت کالا ثبت می‌شود.")
    if amount < 0 or amount > req.order.total:
        raise ReturnError("مبلغ بازپرداخت نامعتبر است.")
    req.refund_amount, req.refund_method, req.refund_reference = amount, method, reference[:100]
    req.refunded_at = timezone.now()
    return _set_status(req, R.Status.REFUNDED, user, note)


@transaction.atomic
def partial_cancel(order, quantities, *, reason, user=None, note=""):
    """لغو بخشی از اقلام سفارشِ هنوز ارسال‌نشده؛ برای لغو همه اقلام، خود سفارش را لغو کنید."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in CANCELLABLE:
        raise ReturnError("لغو بخشی فقط پیش از ارسال سفارش ممکن است.")
    clean = _validated(order, quantities)
    remaining = sum(i.returnable_quantity for i in order.items.all()) - sum(clean.values())
    if remaining <= 0:
        raise ReturnError("همه اقلام انتخاب شده‌اند؛ به‌جای لغو بخشی، کل سفارش را لغو کنید.")
    gross = sum(item.unit_price * qty for item, qty in clean.items())
    amount = refund_for(order, clean)
    paid = order.paid_at is not None
    req = ReturnRequest.objects.create(
        order=order, kind=R.Kind.CANCEL, reason=reason, description=note[:1000], refund_amount=amount if paid else 0,
        status=R.Status.RECEIVED if paid else R.Status.CLOSED, handled_by=user,
        staff_note="" if paid else f"مبلغ سفارش {amount:,} تومان کم شد (هنوز پرداخت نشده بود).")
    ReturnItem.objects.bulk_create([ReturnItem(request=req, order_item=item, quantity=qty) for item, qty in clean.items()])
    _restock(req, user, "لغو بخشی از سفارش")
    req.save(update_fields=["restocked"])
    discount_share = gross - amount
    order.subtotal -= gross
    order.discount = max(order.discount - discount_share, 0)
    order.total = max(order.total - amount, 0)
    order.save(update_fields=["subtotal", "discount", "total"])
    items = "، ".join(f"{i.product_name} × {q}" for i, q in clean.items())
    OrderStatusHistory.objects.create(order=order, from_status=order.status, to_status=order.status, changed_by=user,
                                      note=f"لغو بخشی: {items}"[:200])
    _notify(req)
    return req
