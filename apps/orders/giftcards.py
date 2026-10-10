"""کارت هدیه خریداری‌شده از سایت (محصول با نوع «کارت هدیه»؛ هر حجم = یک مبلغ).

پس از پرداخت سفارش (یا تحویل، برای پرداخت در محل) برای هر عدد یک کارت با مبلغ همان قلم صادر و کد آن با پیامک
برای خریدار فرستاده می‌شود. با لغو سفارش، کارت‌هایی که هنوز خرج نشده‌اند غیرفعال می‌شوند.
"""

from django.db import transaction
from django.db.models import F

from apps.catalog.profile import Kind
from apps.discounts import credits
from apps.discounts.models import GiftCard

from .signals import gift_cards_issued


def issue_purchased(order):
    cards = []
    items = order.items.select_related("variant__product").filter(variant__product__kind=Kind.GIFT_CARD)
    for item in items:
        for _ in range(item.quantity - item.returned_quantity):
            cards.append(credits.issue_card(
                order.store, item.unit_price, source=GiftCard.Source.PURCHASE, order_number=order.number,
                recipient_phone=order.phone, sender_name=order.gift_from or order.full_name,
                message=order.gift_message))
    if cards:
        transaction.on_commit(lambda: gift_cards_issued.send(sender=GiftCard, order=order, cards=cards))
    return cards


def void_purchased(order):
    return GiftCard.objects.filter(store=order.store, order_number=order.number, source=GiftCard.Source.PURCHASE,
                                   is_active=True).filter(balance=F("initial_amount")).update(is_active=False)


def cards_for(order):
    return GiftCard.objects.filter(store=order.store, order_number=order.number, source=GiftCard.Source.PURCHASE)
