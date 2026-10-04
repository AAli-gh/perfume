"""اتصال به سیگنال‌های سفارش (orders هرگز این ماژول را import نمی‌کند)."""

from django.dispatch import receiver

from apps.orders.signals import order_placed, order_status_changed

from . import events as E
from .tasks import notify_order_task


@receiver(order_placed)
def _order_placed(sender, order, **kwargs):
    notify_order_task.delay(order.pk, E.ORDER_PLACED)


@receiver(order_status_changed)
def _status_changed(sender, order, to_status, **kwargs):
    event = E.STATUS_EVENTS.get(to_status)
    if event:
        notify_order_task.delay(order.pk, event)
