"""ثبت سفارش از روی سبد خرید."""

from django.db import transaction
from django.db.models import F

from apps.catalog.models import ProductVariant

from .models import Coupon, Order, OrderItem


class OutOfStock(Exception):
    def __init__(self, names):
        self.names = names
        super().__init__(", ".join(names))


@transaction.atomic
def create_order(cart, form, user=None):
    lines = list(cart)
    variants = {
        v.pk: v
        for v in ProductVariant.objects.select_for_update().select_related("product").filter(
            pk__in=[line.variant.pk for line in lines]
        )
    }
    short = [f"{v.product.name} ({v.size_ml} میل)" for line in lines if (v := variants[line.variant.pk]).stock < line.quantity]
    if short:
        raise OutOfStock(short)

    coupon = cart.coupon
    order = form.save(commit=False)
    order.user = user if user and user.is_authenticated else None
    order.subtotal = cart.subtotal
    order.discount = cart.discount
    order.shipping = cart.shipping
    order.total = cart.total
    order.coupon_code = coupon.code if coupon else ""
    order.save()

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order, variant=line.variant, product_name=line.product.name,
            size_ml=line.variant.size_ml, unit_price=line.unit_price, quantity=line.quantity,
        )
        for line in lines
    ])
    for line in lines:
        ProductVariant.objects.filter(pk=line.variant.pk).update(stock=F("stock") - line.quantity)
    if coupon:
        Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)
    return order


def change_status(order, new_status):
    """تغییر وضعیت سفارش؛ با لغو سفارش، موجودی کالاها به انبار برمی‌گردد.

    منطق کسب‌وکار اینجاست (نه در Admin) تا از هر مسیری — پنل، API یا Task — یکسان اجرا شود.
    """
    previous = Order.objects.filter(pk=order.pk).values_list("status", flat=True).first()
    order.status = new_status
    if previous != new_status and new_status == Order.Status.CANCELLED:
        order.restock()
    return order
