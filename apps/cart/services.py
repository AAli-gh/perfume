"""سرویس‌های سبد خرید."""

from dataclasses import dataclass

from apps.core.forms import en_digits
from apps.discounts.selectors import find_coupon

from .cart import Cart


@dataclass
class CouponResult:
    ok: bool
    message: str


def apply_coupon_code(cart: Cart, raw_code: str) -> CouponResult:
    """اعتبارسنجی و اعمال کد تخفیف روی سبد."""
    code = en_digits(raw_code or "").upper()
    if not code:
        return CouponResult(False, "کد تخفیف را وارد کنید.")
    coupon = find_coupon(cart.store, code)
    if coupon is None:
        return CouponResult(False, "کد تخفیف معتبر نیست.")
    if err := coupon.check_usable(cart.subtotal):
        return CouponResult(False, err)
    cart.apply_coupon(coupon)
    return CouponResult(True, f"کد {coupon.code} اعمال شد.")
