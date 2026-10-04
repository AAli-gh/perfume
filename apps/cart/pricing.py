"""محاسبه قیمت سبد/سفارش — تنها نقطه محاسبه جمع، تخفیف، هزینه ارسال و مبلغ نهایی.

سبد خرید (نمایش) و ثبت سفارش (ذخیره) هر دو از همین تابع استفاده می‌کنند تا عددها هرگز متفاوت نشوند.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceBreakdown:
    subtotal: int
    discount: int
    shipping: int
    total: int
    coupon: object = None  # Coupon اعمال‌شده یا None


def calculate(lines, store_config, coupon=None, shipping_method=None, province="") -> PriceBreakdown:
    """lines: اقلامی با unit_price و quantity؛ store_config: StoreSettings؛ coupon: Coupon یا None.

    shipping_method: روش ارسال (هر شیئی با cost_for(province, amount))؛ None یعنی هزینه ثابت تنظیمات فروشگاه.
    """
    subtotal = sum(line.unit_price * line.quantity for line in lines)
    if coupon is not None and coupon.check_usable(subtotal):
        coupon = None  # کد برای این سبد معتبر نیست
    discount = coupon.discount_for(subtotal) if coupon else 0
    if subtotal == 0:
        shipping = 0
    elif shipping_method is not None:
        shipping = shipping_method.cost_for(province, subtotal - discount)
    elif store_config.free_shipping_over and subtotal - discount >= store_config.free_shipping_over:
        shipping = 0
    else:
        shipping = store_config.shipping_cost
    return PriceBreakdown(subtotal, discount, shipping, subtotal - discount + shipping, coupon)
