from django import template

from ..services import successful_payment

register = template.Library()


@register.simple_tag
def order_payment(order):
    """آخرین پرداخت موفق سفارش (برای نمایش کد پیگیری)."""
    return successful_payment(order)
