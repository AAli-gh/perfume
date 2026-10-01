"""سرویس‌های سبد خرید."""

from dataclasses import dataclass

from apps.core.forms import en_digits

from .cart import Cart


@dataclass
class CouponResult:
    ok: bool
    message: str


def apply_coupon_code(cart: Cart, raw_code: str) -> CouponResult:
    """اعتبارسنجی و اعمال کد تخفیف روی سبد."""
    # TODO(Phase 2): با انتقال Coupon به اپ discounts، این وابستگی cart → orders حذف می‌شود.
    from apps.orders.models import Coupon

    code = en_digits(raw_code or "").upper()
    if not code:
        return CouponResult(False, "کد تخفیف را وارد کنید.")
    coupon = Coupon.objects.filter(code=code).first()
    if coupon is None:
        return CouponResult(False, "کد تخفیف معتبر نیست.")
    if err := coupon.check_usable(cart.subtotal):
        return CouponResult(False, err)
    cart.apply_coupon(coupon)
    return CouponResult(True, f"کد {coupon.code} اعمال شد.")
