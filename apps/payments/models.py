from django.db import models

from apps.core.models import StoreOwned, StoreQuerySet


class GatewayAccount(StoreOwned):
    """درگاه پرداخت فعال یک فروشگاه و اطلاعات اتصال آن."""

    gateway = models.CharField("درگاه", max_length=30, help_text="کد درگاه، مثلاً zarinpal")
    title = models.CharField("عنوان نمایشی", max_length=80, default="پرداخت آنلاین")
    merchant_id = models.CharField("مرچنت کد", max_length=100, blank=True)
    sandbox = models.BooleanField("حالت آزمایشی (Sandbox)", default=False)
    is_active = models.BooleanField("فعال", default=True)
    priority = models.PositiveSmallIntegerField("اولویت", default=0)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["priority", "id"]
        verbose_name = "حساب درگاه پرداخت"
        verbose_name_plural = "حساب‌های درگاه پرداخت"
        constraints = [
            models.UniqueConstraint(fields=["store", "gateway"], name="payments_one_account_per_gateway"),
        ]

    def __str__(self):
        return f"{self.title} ({self.gateway})"


class Payment(models.Model):
    """یک تلاش پرداخت برای یک سفارش. هر سفارش می‌تواند چند تلاش (ناموفق/موفق) داشته باشد."""

    class Status(models.TextChoices):
        INITIATED = "initiated", "ایجاد شده"
        PENDING = "pending", "در انتظار بازگشت از درگاه"
        SUCCEEDED = "succeeded", "موفق"
        FAILED = "failed", "ناموفق"
        CANCELLED = "cancelled", "انصراف کاربر"
        EXPIRED = "expired", "منقضی (سفارش دیگر قابل پرداخت نبود)"

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments", verbose_name="سفارش")
    gateway = models.CharField("درگاه", max_length=30)
    amount = models.PositiveIntegerField("مبلغ (تومان)")
    status = models.CharField("وضعیت", max_length=12, choices=Status.choices, default=Status.INITIATED)
    authority = models.CharField("شناسه تراکنش درگاه", max_length=100, blank=True, db_index=True)
    ref_id = models.CharField("کد پیگیری", max_length=100, blank=True)
    card_pan = models.CharField("کارت (ماسک‌شده)", max_length=30, blank=True)
    message = models.CharField("پیام", max_length=255, blank=True)
    raw = models.JSONField("پاسخ‌های درگاه", default=dict, blank=True)
    created_at = models.DateTimeField("ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("به‌روزرسانی", auto_now=True)
    verified_at = models.DateTimeField("تأیید", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
        constraints = [
            models.UniqueConstraint(
                fields=["gateway", "authority"], condition=~models.Q(authority=""), name="payments_unique_authority"
            ),
        ]

    def __str__(self):
        return f"{self.order} — {self.get_status_display()}"
