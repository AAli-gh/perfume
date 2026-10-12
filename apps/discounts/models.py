from django.conf import settings
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


class GiftCard(StoreOwned):
    """کارت هدیه با مانده قابل خرج در چند خرید (صدور از پنل، خرید از سایت یا بازپرداخت مرجوعی)."""

    class Source(models.TextChoices):
        MANUAL = "manual", "صدور توسط فروشگاه"
        PURCHASE = "purchase", "خرید مشتری"
        REFUND = "refund", "بازپرداخت مرجوعی"

    code = models.CharField("کد", max_length=20)
    initial_amount = models.PositiveIntegerField("مبلغ اولیه (تومان)")
    balance = models.PositiveIntegerField("مانده (تومان)")
    expires_at = models.DateTimeField("انقضا", null=True, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    source = models.CharField("منبع", max_length=10, choices=Source.choices, default=Source.MANUAL)
    order_number = models.CharField("سفارش مرتبط", max_length=20, blank=True, db_index=True)
    recipient_name = models.CharField("نام گیرنده", max_length=80, blank=True)
    recipient_phone = models.CharField("موبایل گیرنده", max_length=11, blank=True)
    sender_name = models.CharField("از طرف", max_length=80, blank=True)
    message = models.CharField("پیام", max_length=200, blank=True)
    created_at = models.DateTimeField("زمان صدور", auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "کارت هدیه"
        verbose_name_plural = "کارت‌های هدیه"
        constraints = [models.UniqueConstraint(fields=["store", "code"], name="discounts_giftcard_unique_code")]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper().replace(" ", "")
        super().save(*args, **kwargs)

    def check_usable(self, now=None):
        now = now or timezone.now()
        if not self.is_active:
            return "این کارت هدیه غیرفعال است."
        if self.expires_at and now > self.expires_at:
            return "مهلت این کارت هدیه تمام شده است."
        if self.balance <= 0:
            return "مانده این کارت هدیه صفر است."
        return None


class GiftCardTransaction(models.Model):
    card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name="transactions", verbose_name="کارت")
    amount = models.IntegerField("مبلغ", help_text="منفی: خرج در سفارش؛ مثبت: شارژ یا برگشت")
    order_number = models.CharField("سفارش", max_length=20, blank=True, db_index=True)
    note = models.CharField("توضیح", max_length=200, blank=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "گردش کارت هدیه"
        verbose_name_plural = "گردش کارت‌های هدیه"

    def __str__(self):
        return f"{self.card} {self.amount:+}"


class LoyaltyAccount(StoreOwned):
    """باشگاه مشتریان: مانده امتیاز هر مشتری عضو (گردش در LoyaltyEntry)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loyalty_accounts",
                             verbose_name="کاربر")
    points = models.IntegerField("امتیاز", default=0)

    objects = StoreQuerySet.as_manager()

    class Meta:
        verbose_name = "حساب امتیاز"
        verbose_name_plural = "حساب‌های امتیاز (باشگاه مشتریان)"
        constraints = [models.UniqueConstraint(fields=["store", "user"], name="discounts_one_loyalty_account")]

    def __str__(self):
        return f"{self.user} — {self.points}"


class LoyaltyEntry(models.Model):
    class Reason(models.TextChoices):
        EARNED = "earned", "خرید"
        REDEEMED = "redeemed", "استفاده در سفارش"
        RESTORED = "restored", "برگشت (لغو سفارش)"
        REVOKED = "revoked", "کسر (لغو/مرجوعی)"
        MANUAL = "manual", "تنظیم دستی"

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name="entries", verbose_name="حساب")
    points = models.IntegerField("امتیاز")
    reason = models.CharField("علت", max_length=10, choices=Reason.choices)
    order_number = models.CharField("سفارش", max_length=20, blank=True, db_index=True)
    note = models.CharField("توضیح", max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="کاربر")
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "گردش امتیاز"
        verbose_name_plural = "گردش امتیازها"

    def __str__(self):
        return f"{self.points:+} {self.get_reason_display()}"
