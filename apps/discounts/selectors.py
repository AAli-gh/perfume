from .models import Coupon


def find_coupon(store, code):
    """کد تخفیف فروشگاه با کد داده‌شده (بدون حساسیت به حروف کوچک/بزرگ)، یا None."""
    code = (code or "").strip().upper()
    return Coupon.objects.for_store(store).filter(code=code).first() if code else None
