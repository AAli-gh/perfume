from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reviews", verbose_name="محصول")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر"
    )
    name = models.CharField("نام", max_length=80)
    rating = models.PositiveSmallIntegerField("امتیاز", validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField("متن نظر")
    is_approved = models.BooleanField("تأیید شده", default=False)
    created_at = models.DateTimeField("تاریخ", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "catalog_review"  # جدول قبلی حفظ شده (انتقال از اپ catalog)
        verbose_name = "نظر"
        verbose_name_plural = "نظرات"

    def __str__(self):
        return f"{self.name} — {self.product}"
