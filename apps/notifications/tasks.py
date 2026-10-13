from celery import shared_task

from .models import NotificationLog


@shared_task(bind=True, max_retries=3, default_retry_delay=120, acks_late=True)
def notify_order_task(self, order_id, event):
    """ارسال پیام‌های یک رویداد سفارش؛ پیام‌های ناموفق تا ۳ بار دوباره تلاش می‌شوند (پیام موفق تکرار نمی‌شود)."""
    from apps.orders.models import Order

    from .services import notify_order

    order = Order.objects.select_related("store", "shipping_method").filter(pk=order_id).first()
    if order is None:
        return 0
    logs = notify_order(order, event)
    if any(entry.status == NotificationLog.FAILED for entry in logs) and self.request.retries < self.max_retries:
        if not self.request.is_eager:
            raise self.retry()
    return sum(entry.status == NotificationLog.SENT for entry in logs)


@shared_task(acks_late=True)
def stock_alert_task(variant_id, event):
    """موجودی کم ← پیام به مدیران؛ موجود شد ← پیامک به همه درخواست‌های باز «خبرم کن» آن حجم."""
    from .stock import alert_low_stock, notify_back_in_stock

    return alert_low_stock(variant_id) if event == "low_stock" else notify_back_in_stock(variant_id)


@shared_task(acks_late=True, time_limit=3600)
def send_campaign_task(campaign_id):
    from .campaigns import send_campaign

    send_campaign(campaign_id)


@shared_task
def send_cart_reminders_task():
    from apps.core.models import Store

    from .cart_reminders import send_reminders

    return sum(send_reminders(store) for store in Store.objects.all())


@shared_task
def send_price_drop_alerts_task():
    from apps.core.models import Store

    from .price_drop import send_alerts

    return sum(send_alerts(store) for store in Store.objects.all())


@shared_task(acks_late=True)
def notify_return_task(request_id, status):
    """پیامک وضعیت مرجوعی به مشتری؛ «درخواست جدید» (ثبت مشتری) به مدیران هم خبر داده می‌شود."""
    from apps.core.templatetags.majd import toman
    from apps.orders.models import ReturnRequest
    from django.urls import reverse

    from . import events as E
    from .services import notify_event

    req = ReturnRequest.objects.select_related("order__store").filter(pk=request_id).first()
    if req is None or req.status != status:
        return 0
    order = req.order
    context = {"name": order.first_name, "number": order.number, "kind": req.get_kind_display(),
               "status": req.get_status_display(), "amount": toman(req.refund_amount),
               "order_url": order.store.base_url + reverse("orders:detail", args=[order.number])}
    audiences = (E.CUSTOMER, E.STAFF) if status == ReturnRequest.Status.REQUESTED and req.by_customer else (E.CUSTOMER,)
    return len(notify_event(order.store, E.RETURN_UPDATE, context, phone=order.phone, audiences=audiences))


@shared_task(acks_late=True)
def gift_card_sms_task(card_ids, phone=""):
    """پیامک کد کارت هدیه به گیرنده (یا خریدار)."""
    from apps.discounts.credits import format_code
    from apps.discounts.models import GiftCard
    from apps.core.templatetags.majd import jdate, toman

    from . import events as E
    from .services import notify_event

    sent = 0
    for card in GiftCard.objects.select_related("store").filter(pk__in=card_ids):
        to = phone or card.recipient_phone
        if not to:
            continue
        context = {"name": card.recipient_name, "code": format_code(card.code), "amount": toman(card.initial_amount),
                   "sender": card.sender_name or card.store.name, "message": card.message,
                   "expires": jdate(card.expires_at) if card.expires_at else "بدون انقضا",
                   "shop_url": card.store.base_url + "/shop/"}
        sent += len(notify_event(card.store, E.GIFT_CARD, context, phone=to, audiences=(E.CUSTOMER,)))
    return sent
