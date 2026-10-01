from django.db.models import F

from .models import Coupon


def record_usage(coupon):
    """ثبت یک‌بار استفاده از کد تخفیف (اتمیک)."""
    Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)
