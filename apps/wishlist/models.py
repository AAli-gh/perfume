from django.conf import settings
from django.db import models


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist", verbose_name="کاربر")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="wishlisted_by", verbose_name="محصول"
    )
    created_at = models.DateTimeField("تاریخ افزودن", auto_now_add=True)
    price_alert = models.BooleanField("خبرم کن وقتی قیمت پایین آمد", default=True)
    price_seen = models.PositiveIntegerField(
        "قیمت مبنا", null=True, blank=True,
        help_text="قیمت هنگام افزودن (یا آخرین اطلاع‌رسانی)؛ کاهش قیمت نسبت به همین سنجیده می‌شود")
    price_alerted_at = models.DateTimeField("آخرین اطلاع کاهش قیمت", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "علاقه‌مندی"
        verbose_name_plural = "علاقه‌مندی‌ها"
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="wishlist_unique_user_product")]

    def __str__(self):
        return f"{self.user} ♥ {self.product}"
