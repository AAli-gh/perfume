"""اتصال به سیگنال‌های سفارش و موجودی (orders و catalog هرگز این ماژول را import نمی‌کنند)."""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.catalog.events import back_in_stock, stock_low
from apps.discounts.signals import referral_rewarded
from apps.orders.signals import gift_cards_issued, order_placed, order_status_changed, return_updated
from apps.reviews.models import Answer, Question

from . import events as E
from .tasks import (
    gift_card_sms_task,
    notify_order_task,
    notify_return_task,
    question_answered_task,
    question_asked_task,
    referral_reward_task,
    stock_alert_task,
)


@receiver(order_placed)
def _order_placed(sender, order, **kwargs):
    notify_order_task.delay(order.pk, E.ORDER_PLACED)


@receiver(order_status_changed)
def _status_changed(sender, order, to_status, **kwargs):
    event = E.STATUS_EVENTS.get(to_status)
    if event:
        notify_order_task.delay(order.pk, event)


@receiver(stock_low)
def _stock_low(sender, variant_id, **kwargs):
    stock_alert_task.delay(variant_id, E.LOW_STOCK)


@receiver(back_in_stock)
def _back_in_stock(sender, variant_id, **kwargs):
    stock_alert_task.delay(variant_id, E.BACK_IN_STOCK)


@receiver(return_updated)
def _return_updated(sender, request, **kwargs):
    notify_return_task.delay(request.pk, request.status)


@receiver(gift_cards_issued)
def _gift_cards_issued(sender, order, cards, **kwargs):
    gift_card_sms_task.delay([card.pk for card in cards])


@receiver(referral_rewarded)
def _referral_rewarded(sender, referral, **kwargs):
    referral_reward_task.delay(referral.pk)


@receiver(post_save, sender=Question)
def _question_asked(sender, instance, created, **kwargs):
    if created and not kwargs.get("raw"):
        transaction.on_commit(lambda: question_asked_task.delay(instance.pk))


@receiver(post_save, sender=Answer)
def _question_answered(sender, instance, created, **kwargs):
    if created and instance.is_staff and not kwargs.get("raw"):
        transaction.on_commit(lambda: question_answered_task.delay(instance.pk))
