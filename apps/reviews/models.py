from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.validators import image_upload


class Review(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reviews", verbose_name="محصول")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر"
    )
    name = models.CharField("نام", max_length=80)
    rating = models.PositiveSmallIntegerField("امتیاز", validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField("متن نظر")
    is_approved = models.BooleanField("تأیید شده", default=False)
    is_verified = models.BooleanField(
        "خریدار تأییدشده", default=False, help_text="نویسنده این محصول را خریده و سفارشش تحویل شده است (خودکار)")
    created_at = models.DateTimeField("تاریخ", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "catalog_review"  # جدول قبلی حفظ شده (انتقال از اپ catalog)
        verbose_name = "نظر"
        verbose_name_plural = "نظرات"

    def __str__(self):
        return f"{self.name} — {self.product}"


class ReviewPhoto(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="photos", verbose_name="نظر")
    image = models.ImageField("عکس", upload_to="reviews/", validators=[image_upload])

    class Meta:
        verbose_name = "عکس نظر"
        verbose_name_plural = "عکس‌های نظر"

    def __str__(self):
        return f"عکس {self.review_id}"


class Question(models.Model):
    """پرسش مشتری زیر محصول؛ پس از پاسخ و تأیید مدیر نمایش داده می‌شود."""

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="questions",
                                verbose_name="محصول")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="product_questions", verbose_name="کاربر")
    name = models.CharField("نام", max_length=80)
    text = models.TextField("پرسش", max_length=1000)
    is_approved = models.BooleanField("نمایش در سایت", default=False)
    created_at = models.DateTimeField("تاریخ", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پرسش"
        verbose_name_plural = "پرسش و پاسخ‌ها"

    def __str__(self):
        return self.text[:60]


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers", verbose_name="پرسش")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="+", verbose_name="پاسخ‌دهنده")
    text = models.TextField("پاسخ", max_length=2000)
    is_staff = models.BooleanField("پاسخ فروشگاه", default=True)
    created_at = models.DateTimeField("تاریخ", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "پاسخ"
        verbose_name_plural = "پاسخ‌ها"

    def __str__(self):
        return self.text[:60]
