"""ثبت سفارش از روی سبد خرید."""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Address
from apps.accounts.services import remember_address
from apps.cart.pricing import calculate
from apps.catalog import inventory
from apps.catalog.inventory import OutOfStock
from apps.discounts.models import Coupon
from apps.discounts.services import record_usage

from .models import Order, OrderItem
from .signals import order_placed

__all__ = ["CouponUnavailable", "OutOfStock", "create_order"]


class CouponUnavailable(Exception):
    """کد تخفیف بین نمایش سبد و ثبت سفارش نامعتبر شده (مثلاً ظرفیتش پر شده)."""


@dataclass(frozen=True)
class _Line:
    variant: object
    quantity: int

    @property
    def unit_price(self):
        return self.variant.price


@transaction.atomic
def create_order(cart, form, user=None):
    """ثبت سفارش به‌صورت اتمیک: رزرو موجودی، قفل کد تخفیف، محاسبه قیمت با داده‌های قفل‌شده."""
    order = form.save(commit=False)
    order.store = cart.store
    order.user = user if user and user.is_authenticated else None
    order.save()  # شماره سفارش برای مرجع گردش موجودی لازم است

    wanted = [(line.variant, line.quantity) for line in cart]
    box = form.cleaned_data.get("gift_box")
    if box is not None:  # باکس هدیه انتخاب‌شده در صفحه تسویه
        wanted.append((box, 1))
    quantities = {}
    for variant, quantity in wanted:
        quantities[variant.pk] = quantities.get(variant.pk, 0) + quantity
    variants = inventory.reserve(
        [inventory.StockLine(pk, quantity) for pk, quantity in quantities.items()], order.number, user=order.user
    )
    lines = [_Line(variants[pk], quantity) for pk, quantity in quantities.items()]

    coupon = None
    if cart.coupon_code:
        # قفل ردیف کد تخفیف: دو سفارش هم‌زمان نمی‌توانند از سقف استفاده عبور کنند
        coupon = Coupon.objects.select_for_update().filter(store=cart.store, code=cart.coupon_code).first()
        subtotal = sum(line.unit_price * line.quantity for line in lines)
        error = "کد تخفیف دیگر معتبر نیست." if coupon is None else coupon.check_usable(subtotal)
        if error:
            raise CouponUnavailable(error)

    method = form.cleaned_data.get("shipping_method")
    pricing = calculate(lines, cart.store.config, coupon, shipping_method=method, province=order.province)
    if method is not None:
        order.shipping_method, order.shipping_method_name = method, method.name
    order.subtotal, order.discount, order.shipping, order.total = (
        pricing.subtotal, pricing.discount, pricing.shipping, pricing.total,
    )
    order.coupon_code = coupon.code if coupon else ""
    if order.payment_method == Order.PaymentMethod.ONLINE:
        order.reserved_until = timezone.now() + timedelta(minutes=cart.store.config.payment_timeout_minutes)
    order.save()

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order, variant=line.variant, product_name=line.variant.product.name,
            size_ml=line.variant.size_ml, unit_price=line.unit_price, quantity=line.quantity,
        )
        for line in lines
    ])
    if coupon:
        record_usage(coupon)
    remember_address(order.user, {f: getattr(order, f) for f in Address.FIELDS})
    transaction.on_commit(lambda: order_placed.send(sender=Order, order=order))
    return order
