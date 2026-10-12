from django.conf import settings
from django.db import models

from apps.core.models import StoreOwned, StoreQuerySet


class SavedCart(StoreOwned):
    """سبد خرید مشتری واردشده در پایگاه داده: بازگرداندن سبد در دستگاه دیگر و یادآوری سبد رهاشده."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_carts",
                             verbose_name="کاربر")
    items = models.JSONField("اقلام", default=dict, help_text="{شناسه حجم: تعداد}")
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True, db_index=True)
    reminded_at = models.DateTimeField("زمان یادآوری", null=True, blank=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "سبد خرید ذخیره‌شده"
        verbose_name_plural = "سبدهای خرید ذخیره‌شده (رهاشده)"
        constraints = [models.UniqueConstraint(fields=["store", "user"], name="cart_one_saved_cart_per_user")]

    def __str__(self):
        return f"سبد {self.user}"

    @property
    def quantity(self):
        return sum(self.items.values())
