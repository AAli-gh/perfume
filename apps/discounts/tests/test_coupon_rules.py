"""قواعد اعتبار کد تخفیف: فعال بودن، بازه زمانی، سقف استفاده و حداقل خرید."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.discounts.models import Coupon

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("extra,message", [
    ({"is_active": False}, "فعال نیست"),
    ({"valid_from": timezone.now() + timedelta(days=1)}, "هنوز نرسیده"),
    ({"valid_to": timezone.now() - timedelta(minutes=1)}, "به پایان رسیده"),
    ({"usage_limit": 2, "used_count": 2}, "تکمیل شده"),
])
def test_unusable_coupons(store, extra, message):
    coupon = Coupon.objects.create(code="x", percent=10, **extra)
    assert message in coupon.check_usable(1_000_000)


def test_usable_coupon_and_code_normalized(store):
    coupon = Coupon.objects.create(code="  majd20 ", percent=20, usage_limit=5, used_count=4,
                                   valid_from=timezone.now() - timedelta(days=1),
                                   valid_to=timezone.now() + timedelta(days=1))
    assert coupon.code == "MAJD20" and str(coupon) == "MAJD20"
    assert coupon.check_usable(1_000_000) is None
