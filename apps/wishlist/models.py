from django.conf import settings
from django.db import models


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist", verbose_name="کاربر")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="wishlisted_by", verbose_name="محصول"
    )
    created_at = models.DateTimeField("تاریخ افزودن", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "علاقه‌مندی"
        verbose_name_plural = "علاقه‌مندی‌ها"
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="wishlist_unique_user_product")]

    def __str__(self):
        return f"{self.user} ♥ {self.product}"
