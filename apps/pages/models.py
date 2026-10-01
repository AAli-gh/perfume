from django.db import models

from apps.core.models import StoreOwned, StoreQuerySet


class ContactMessage(StoreOwned):
    class Subject(models.TextChoices):
        ADVICE = "advice", "مشاوره انتخاب عطر"
        ORDER = "order", "پیگیری سفارش"
        RETURN = "return", "بازگشت و تعویض"
        BUSINESS = "business", "همکاری و فروش سازمانی"
        OTHER = "other", "سایر موارد"

    name = models.CharField("نام", max_length=100)
    email = models.EmailField("ایمیل")
    subject = models.CharField("موضوع", max_length=20, choices=Subject.choices, default=Subject.ADVICE)
    message = models.TextField("پیام")
    is_read = models.BooleanField("خوانده شده", default=False)
    created_at = models.DateTimeField("تاریخ", auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        db_table = "core_contactmessage"  # جدول قبلی حفظ شده (انتقال از اپ core)
        verbose_name = "پیام تماس"
        verbose_name_plural = "پیام‌های تماس"

    def __str__(self):
        return f"{self.name} — {self.get_subject_display()}"
