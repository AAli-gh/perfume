from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import StoreOwned, StoreQuerySet


class Coupon(StoreOwned):
    code = models.CharField("کد", max_length=30)
    percent = models.PositiveSmallIntegerField("درصد تخفیف", validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_discount = models.PositiveIntegerField("سقف تخفیف (تومان)", null=True, blank=True)
    min_subtotal = models.PositiveIntegerField("حداقل مبلغ سبد (تومان)", default=0)
    valid_from = models.DateTimeField("شروع اعتبار", null=True, blank=True)
    valid_to = models.DateTimeField("پایان اعتبار", null=True, blank=True)
    usage_limit = models.PositiveIntegerField("سقف استفاده", null=True, blank=True)
    used_count = models.PositiveIntegerField("تعداد استفاده", default=0, editable=False)
    is_active = models.BooleanField("فعال", default=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        db_table = "orders_coupon"  # جدول قبلی حفظ شده (انتقال از اپ orders)
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"
        constraints = [
            models.UniqueConstraint(fields=["store", "code"], name="discounts_coupon_unique_code_per_store"),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def check_usable(self, subtotal):
        """اگر کد قابل استفاده نباشد، پیام خطا برمی‌گرداند؛ در غیر این صورت None."""
        now = timezone.now()
        if not self.is_active:
            return "این کد تخفیف فعال نیست."
        if self.valid_from and now < self.valid_from:
            return "زمان استفاده از این کد هنوز نرسیده است."
        if self.valid_to and now > self.valid_to:
            return "مهلت استفاده از این کد به پایان رسیده است."
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return "ظرفیت استفاده از این کد تکمیل شده است."
        if subtotal < self.min_subtotal:
            return "مبلغ سبد خرید برای استفاده از این کد کافی نیست."
        return None

    def discount_for(self, subtotal):
        amount = subtotal * self.percent // 100
        if self.max_discount is not None:
            amount = min(amount, self.max_discount)
        return amount
