from django.db import models
from django.db.models import Q

from apps.core.models import StoreOwned, StoreQuerySet
from apps.core.stores import default_store_id


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


class Page(StoreOwned):
    """صفحه‌ای که از بخش‌های قابل مدیریت ساخته می‌شود (فعلاً صفحه اصلی؛ صفحات دیگر در آینده)."""

    # چیدمان صفحه جزو تنظیمات فروشگاه است (نه داده تجاری) ← با حذف فروشگاه حذف می‌شود
    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه",
                              default=default_store_id)
    title = models.CharField("عنوان", max_length=150)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=160)
    is_home = models.BooleanField("صفحه اصلی", default=False)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-is_home", "title"]
        verbose_name = "صفحه"
        verbose_name_plural = "صفحه‌ها (سازنده صفحه)"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="pages_page_unique_slug_per_store"),
            models.UniqueConstraint(fields=["store"], condition=Q(is_home=True), name="pages_one_home_per_store"),
        ]

    def __str__(self):
        return self.title


class PageSection(models.Model):
    class Status(models.TextChoices):
        PUBLISHED = "published", "منتشرشده"
        DRAFT = "draft", "پیش‌نویس"

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="sections", verbose_name="صفحه")
    type = models.CharField("نوع بخش", max_length=40)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.PUBLISHED)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)
    is_enabled = models.BooleanField("فعال", default=True)
    settings = models.JSONField("تنظیمات", default=dict, blank=True)
    image = models.ImageField("تصویر", upload_to="pages/sections/", blank=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "بخش صفحه"
        verbose_name_plural = "بخش‌های صفحه"
        indexes = [models.Index(fields=["page", "status", "order"])]

    def __str__(self):
        section_type = self.section_type
        return section_type.label if section_type else self.type

    @property
    def section_type(self):
        from .sections import get

        return get(self.type)

    def clean(self):
        from django.core.exceptions import ValidationError

        section_type = self.section_type
        if section_type is None:
            raise ValidationError({"type": "نوع بخش ناشناخته است."})
        try:
            self.settings = section_type.clean_settings(self.settings)
        except ValidationError as exc:
            raise ValidationError({"settings": [f"{k}: {', '.join(map(str, v))}" for k, v in exc.message_dict.items()]}) from exc
