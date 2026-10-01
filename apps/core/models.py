from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from .stores import default_store_id


class Store(models.Model):
    """فروشگاه (Tenant). همه داده‌های اصلی فروشگاه به یک Store تعلق دارند.

    فعلاً یک فروشگاه پیش‌فرض وجود دارد؛ ساختار برای چند فروشگاه (White-Label) آماده است.
    """

    name = models.CharField("نام فروشگاه", max_length=120)
    code = models.SlugField("کد", max_length=50, unique=True)
    is_default = models.BooleanField("فروشگاه پیش‌فرض", default=False)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name = "فروشگاه"
        verbose_name_plural = "فروشگاه‌ها"
        constraints = [
            models.UniqueConstraint(fields=["is_default"], condition=Q(is_default=True), name="core_single_default_store"),
        ]

    def __str__(self):
        return self.name


class StoreDomain(models.Model):
    """دامنه‌هایی که به یک فروشگاه اشاره می‌کنند (برای تشخیص فروشگاه از روی Host)."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="domains", verbose_name="فروشگاه")
    domain = models.CharField("دامنه", max_length=253, unique=True, help_text="بدون http و پورت؛ مثلاً shop.example.com")
    is_primary = models.BooleanField("دامنه اصلی", default=False)

    class Meta:
        verbose_name = "دامنه فروشگاه"
        verbose_name_plural = "دامنه‌های فروشگاه"

    def __str__(self):
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = self.domain.strip().lower()
        super().save(*args, **kwargs)


class StoreSettings(models.Model):
    """اطلاعات و تنظیمات کسب‌وکار هر فروشگاه که مدیر بدون تغییر کد عوض می‌کند.

    تنظیمات ظاهری (رنگ، لوگو، Theme) جدا هستند و در اپ themes نگه داشته می‌شوند.
    """

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="config", verbose_name="فروشگاه")
    tagline = models.CharField("شعار", max_length=200, blank=True)
    email = models.EmailField("ایمیل", blank=True)
    phone = models.CharField("تلفن (نمایشی)", max_length=30, blank=True)
    phone_link = models.CharField(
        "تلفن (برای لینک)", max_length=20, blank=True,
        validators=[RegexValidator(r"^\+?\d{6,15}$", "فقط رقم، با + اختیاری؛ مثلاً +982112345678")],
    )
    address = models.CharField("نشانی", max_length=300, blank=True)
    instagram_url = models.CharField("اینستاگرام", max_length=200, blank=True)
    telegram_url = models.CharField("تلگرام", max_length=200, blank=True)
    whatsapp_url = models.CharField("واتس‌اپ", max_length=200, blank=True)
    shipping_cost = models.PositiveIntegerField("هزینه ارسال (تومان)", default=0)
    free_shipping_over = models.PositiveIntegerField(
        "ارسال رایگان برای سفارش‌های بالای (تومان)", default=0, help_text="۰ یعنی غیرفعال"
    )
    currency_label = models.CharField("واحد پول (نمایشی)", max_length=20, default="تومان")
    payment_timeout_minutes = models.PositiveSmallIntegerField(
        "مهلت پرداخت آنلاین (دقیقه)", default=30,
        help_text="بعد از این مدت سفارش پرداخت‌نشده لغو و موجودی آن آزاد می‌شود",
    )
    bank_card_number = models.CharField("شماره کارت (کارت به کارت)", max_length=30, blank=True)
    bank_card_holder = models.CharField("نام صاحب کارت", max_length=100, blank=True)

    class Meta:
        verbose_name = "تنظیمات فروشگاه"
        verbose_name_plural = "تنظیمات فروشگاه"

    def __str__(self):
        return f"تنظیمات {self.store}"

    def as_site_context(self):
        """داده‌های عمومی فروشگاه برای قالب‌ها (متغیر SITE)."""
        return {
            "name": self.store.name,
            "tagline": self.tagline,
            "phone": self.phone,
            "phone_link": self.phone_link,
            "email": self.email,
            "address": self.address,
            "instagram": self.instagram_url or "#",
            "telegram": self.telegram_url or "#",
            "whatsapp": self.whatsapp_url or "#",
            "bank_card_number": self.bank_card_number,
            "bank_card_holder": self.bank_card_holder or self.store.name,
        }


class StoreQuerySet(models.QuerySet):
    def for_store(self, store):
        return self.filter(store=store)


class StoreOwned(models.Model):
    """پایه مدل‌هایی که به یک فروشگاه تعلق دارند (Product، Order، Post، …).

    پیش‌فرض فیلد store، فروشگاه جاری (یا پیش‌فرض) است تا کد تک‌فروشگاهی فعلی بدون تغییر کار کند.
    """

    store = models.ForeignKey(
        "core.Store", on_delete=models.PROTECT, related_name="+", verbose_name="فروشگاه",
        default=default_store_id,
    )

    class Meta:
        abstract = True
