from django.db import models

from apps.core.models import StoreOwned, StoreQuerySet


class NewsletterSubscriber(StoreOwned):
    email = models.EmailField("ایمیل")
    created_at = models.DateTimeField("تاریخ عضویت", auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        db_table = "core_newslettersubscriber"  # جدول قبلی حفظ شده (انتقال از اپ core)
        verbose_name = "عضو خبرنامه"
        verbose_name_plural = "اعضای خبرنامه"
        constraints = [
            models.UniqueConstraint(fields=["store", "email"], name="marketing_newslettersubscriber_unique_email_per_store"),
        ]

    def __str__(self):
        return self.email
