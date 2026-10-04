"""پیش‌نویس، انتشار و تاریخچه نسخه‌های ظاهر فروشگاه.

- Workspace: وضعیت پیش‌نویس هر فروشگاه (کلید لینک‌های پیش‌نمایش). با هر انتشار یا کنار گذاشتن
  تغییرات کلید عوض می‌شود تا لینک‌های پیش‌نمایش قبلی باطل شوند.
- Revision: عکس کامل (snapshot) ظاهر و صفحه‌ها در لحظه هر انتشار؛ برای بازگشت به نسخه قبلی.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.core.models import StoreQuerySet


class Workspace(models.Model):
    store = models.OneToOneField("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه")
    preview_key = models.UUIDField("کلید پیش‌نمایش", default=uuid.uuid4)
    updated_at = models.DateTimeField("آخرین ویرایش", auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="آخرین ویرایشگر")

    class Meta:
        verbose_name = "پیش‌نویس فروشگاه"
        verbose_name_plural = "پیش‌نویس‌های فروشگاه"

    def __str__(self):
        return f"پیش‌نویس {self.store}"


class Revision(models.Model):
    class Kind(models.TextChoices):
        BASELINE = "baseline", "نسخه اولیه"
        PUBLISH = "publish", "انتشار"

    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه")
    number = models.PositiveIntegerField("شماره نسخه")
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.PUBLISH)
    label = models.CharField("توضیح", max_length=120, blank=True)
    snapshot = models.JSONField("محتوا", default=dict)
    changes = models.JSONField("بخش‌های تغییرکرده", default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="منتشرکننده")
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-number"]
        verbose_name = "نسخه منتشرشده"
        verbose_name_plural = "تاریخچه انتشار"
        constraints = [models.UniqueConstraint(fields=["store", "number"], name="builder_unique_revision_number")]
        permissions = [("publish_site", "انتشار تغییرات ظاهر و صفحه‌ها")]

    def __str__(self):
        return f"نسخه {self.number} — {self.store}"
