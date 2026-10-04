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
