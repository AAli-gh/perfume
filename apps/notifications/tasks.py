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
