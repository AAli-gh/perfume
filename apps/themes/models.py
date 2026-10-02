"""مدل‌های Theme Engine.

- Theme: یک پوسته نصب‌شده (پوشه themes/<code>/ روی دیسک)؛ سراسری، بین فروشگاه‌ها مشترک.
- ThemePreset: مجموعه‌ای آماده از توکن‌های طراحی (رنگ، تایپوگرافی، فاصله، گردی گوشه، …) برای یک پوسته.
- ThemeSettings: انتخاب و شخصی‌سازی پوسته برای هر فروشگاه؛ یک نسخه «منتشرشده» و یک «پیش‌نویس».
"""

from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import StoreOwned, StoreQuerySet
from apps.core.stores import default_store_id

theme_code_validator = RegexValidator(r"^[a-z][a-z0-9_-]{1,39}$", "کد پوسته فقط حروف کوچک انگلیسی، رقم، - و _")


class Theme(models.Model):
    code = models.CharField("کد", max_length=40, unique=True, validators=[theme_code_validator])
    name = models.CharField("نام", max_length=80)
    description = models.TextField("توضیحات", blank=True)
    version = models.CharField("نسخه", max_length=20, default="1.0.0")
    manifest = models.JSONField("مشخصات (theme.json)", default=dict, blank=True)
    is_available = models.BooleanField("قابل انتخاب", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "پوسته"
        verbose_name_plural = "پوسته‌ها"

    def __str__(self):
        return self.name


class ThemePreset(models.Model):
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name="presets", verbose_name="پوسته")
    code = models.CharField("کد", max_length=40, validators=[theme_code_validator])
    name = models.CharField("نام", max_length=80)
    tokens = models.JSONField("توکن‌های طراحی", default=dict, blank=True)
    is_default = models.BooleanField("پیش‌فرض پوسته", default=False)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    def clean(self):
        from django.core.exceptions import ValidationError

        from . import tokens

        try:
            tokens.validate(self.tokens, partial=True)
        except ValidationError as exc:
            raise ValidationError({"tokens": exc.messages}) from exc

    class Meta:
        ordering = ["theme", "order", "name"]
        verbose_name = "پیش‌تنظیم پوسته"
        verbose_name_plural = "پیش‌تنظیم‌های پوسته"
        constraints = [models.UniqueConstraint(fields=["theme", "code"], name="themes_unique_preset_code")]

    def __str__(self):
        return f"{self.theme.name} — {self.name}"


class ThemeSettings(StoreOwned):
    class Status(models.TextChoices):
        PUBLISHED = "published", "منتشرشده"
        DRAFT = "draft", "پیش‌نویس"

    # تنظیمات خود فروشگاه است (نه داده تجاری) ← با حذف فروشگاه حذف می‌شود
    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه",
                              default=default_store_id)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.PUBLISHED)
    theme = models.ForeignKey(Theme, on_delete=models.PROTECT, related_name="+", verbose_name="پوسته")
    preset = models.ForeignKey(
        ThemePreset, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="پیش‌تنظیم"
    )
    overrides = models.JSONField(
        "شخصی‌سازی توکن‌ها", default=dict, blank=True, help_text="روی توکن‌های پیش‌تنظیم اعمال می‌شود"
    )
    logo = models.ImageField("لوگو", upload_to="themes/logos/", blank=True)
    favicon = models.ImageField("فاوآیکون", upload_to="themes/favicons/", blank=True)
    header = models.JSONField("تنظیمات هدر", default=dict, blank=True)
    footer = models.JSONField("تنظیمات فوتر", default=dict, blank=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)
    published_at = models.DateTimeField("زمان انتشار", null=True, blank=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        verbose_name = "تنظیمات ظاهر فروشگاه"
        verbose_name_plural = "تنظیمات ظاهر فروشگاه‌ها"
        constraints = [models.UniqueConstraint(fields=["store", "status"], name="themes_one_settings_per_status")]

    def __str__(self):
        return f"{self.store} — {self.theme} ({self.get_status_display()})"

    def clean(self):
        from django.core.exceptions import ValidationError

        from . import tokens

        if self.preset_id and self.preset.theme_id != self.theme_id:
            raise ValidationError({"preset": "این پیش‌تنظیم متعلق به پوسته انتخاب‌شده نیست."})
        try:
            tokens.validate(self.overrides, partial=True)
        except ValidationError as exc:
            raise ValidationError({"overrides": exc.messages}) from exc
