from django.core.exceptions import ValidationError
from django.db import models

from apps.core.geo import PROVINCE_CHOICES
from apps.core.models import StoreQuerySet
from apps.core.stores import default_store_id

from .carriers import carrier_choices, get_carrier_class


class ShippingMethod(models.Model):
    """روش ارسال یک فروشگاه (پست پیشتاز، تیپاکس، پیک تهران، …) با نرخ پایه و نرخ هر استان.

    اگر فروشگاه هیچ روش ارسال فعالی نداشته باشد، «هزینه ارسال» و «ارسال رایگان» تنظیمات فروشگاه استفاده می‌شود.
    """

    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه",
                              default=default_store_id)
    name = models.CharField("عنوان", max_length=80, help_text="به مشتری نمایش داده می‌شود؛ مثلاً «پست پیشتاز»")
    description = models.CharField("توضیح", max_length=200, blank=True, help_text="مثلاً «۲ تا ۴ روز کاری»")
    carrier = models.CharField("شرکت حمل / اتصال", max_length=30, default="manual")
    cost = models.PositiveIntegerField("هزینه پایه (تومان)", default=0)
    free_over = models.PositiveIntegerField(
        "رایگان برای سفارش‌های بالای (تومان)", null=True, blank=True,
        help_text="مبلغ پس از تخفیف؛ خالی یعنی هیچ‌وقت رایگان نیست",
    )
    provinces = models.JSONField(
        "فقط این استان‌ها", default=list, blank=True,
        help_text="خالی یعنی همه استان‌ها؛ برای پیک شهری فقط استان خودتان را انتخاب کنید",
    )
    tracking_url_template = models.CharField(
        "الگوی پیوند پیگیری", max_length=300, blank=True,
        help_text="{code} با کد رهگیری جایگزین می‌شود؛ مثلاً https://example.com/track?id={code}",
    )
    api_key = models.CharField("کلید API", max_length=200, blank=True)
    api_secret = models.CharField("رمز API", max_length=200, blank=True)
    account_id = models.CharField("شناسه حساب / قرارداد", max_length=100, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    priority = models.PositiveSmallIntegerField("اولویت", default=0, help_text="عدد کوچک‌تر = بالاتر در فهرست")

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["priority", "id"]
        verbose_name = "روش ارسال"
        verbose_name_plural = "روش‌های ارسال"

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if self.carrier not in dict(carrier_choices()):
            errors["carrier"] = "شرکت حمل ناشناخته است."
        valid = dict(PROVINCE_CHOICES)
        if not isinstance(self.provinces, list) or any(p not in valid for p in self.provinces):
            errors["provinces"] = "استان نامعتبر است."
        if self.tracking_url_template and not self.tracking_url_template.startswith("https://"):
            errors["tracking_url_template"] = "پیوند پیگیری باید با https:// شروع شود."
        if errors:
            raise ValidationError(errors)

    @property
    def carrier_adapter(self):
        return get_carrier_class(self.carrier)(self)

    def serves(self, province):
        return not self.provinces or not province or province in self.provinces

    def cost_for(self, province="", amount=0):
        """هزینه ارسال به تومان برای استان و مبلغ (پس از تخفیف) داده‌شده."""
        if self.free_over is not None and amount >= self.free_over:
            return 0
        quoted = self.carrier_adapter.quote(province=province, amount=amount)
        if quoted is not None:
            return quoted
        rate = next((r.cost for r in self.rates.all() if r.province == province), None) if province else None
        return self.cost if rate is None else rate

    def tracking_url(self, code):
        return self.carrier_adapter.tracking_url(code)


class ProvinceRate(models.Model):
    method = models.ForeignKey(ShippingMethod, on_delete=models.CASCADE, related_name="rates", verbose_name="روش ارسال")
    province = models.CharField("استان", max_length=50, choices=PROVINCE_CHOICES)
    cost = models.PositiveIntegerField("هزینه (تومان)")

    class Meta:
        verbose_name = "نرخ استان"
        verbose_name_plural = "نرخ استان‌ها (جایگزین هزینه پایه)"
        constraints = [models.UniqueConstraint(fields=["method", "province"], name="shipping_one_rate_per_province")]

    def __str__(self):
        return f"{self.province}: {self.cost}"
