import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import StoreOwned, StoreQuerySet
from apps.core.validators import iran_mobile_validator as phone_validator
from apps.core.validators import postal_code_validator as postal_validator


class Order(StoreOwned):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار پرداخت"
        PAID = "paid", "پرداخت شده"
        PROCESSING = "processing", "در حال آماده‌سازی"
        SHIPPED = "shipped", "ارسال شده"
        DELIVERED = "delivered", "تحویل شده"
        CANCELLED = "cancelled", "لغو شده"

    class PaymentMethod(models.TextChoices):
        ONLINE = "online", "پرداخت آنلاین"
        CARD = "card", "کارت به کارت"
        COD = "cod", "پرداخت در محل"

    number = models.CharField("شماره سفارش", max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders", verbose_name="کاربر",
    )
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField("روش پرداخت", max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.ONLINE)

    first_name = models.CharField("نام", max_length=80)
    last_name = models.CharField("نام خانوادگی", max_length=80)
    phone = models.CharField("موبایل", max_length=11, validators=[phone_validator])
    email = models.EmailField("ایمیل", blank=True)
    province = models.CharField("استان", max_length=50)
    city = models.CharField("شهر", max_length=80)
    address = models.CharField("نشانی", max_length=300)
    postal_code = models.CharField("کد پستی", max_length=10, validators=[postal_validator])
    note = models.TextField("توضیحات", blank=True)

    subtotal = models.PositiveIntegerField("جمع جزء", default=0)
    discount = models.PositiveIntegerField("تخفیف", default=0)
    shipping = models.PositiveIntegerField("هزینه ارسال", default=0)
    total = models.PositiveIntegerField("مبلغ نهایی", default=0)
    coupon_code = models.CharField("کد تخفیف", max_length=30, blank=True)

    payment_authority = models.CharField("شناسه پرداخت", max_length=64, blank=True, db_index=True)
    payment_ref_id = models.CharField("کد پیگیری", max_length=64, blank=True)
    paid_at = models.DateTimeField("زمان پرداخت", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = "MJ" + timezone.now().strftime("%y%m") + secrets.token_hex(3).upper()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("orders:detail", args=[self.number])

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_paid(self):
        return self.paid_at is not None

    def restock(self):
        """بازگرداندن موجودی کالاها (هنگام لغو یا پرداخت ناموفق)."""
        from apps.catalog.models import ProductVariant

        for item in self.items.exclude(variant=None):
            ProductVariant.objects.filter(pk=item.variant_id).update(stock=models.F("stock") + item.quantity)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="سفارش")
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کالا"
    )
    product_name = models.CharField("نام محصول", max_length=150)
    size_ml = models.PositiveSmallIntegerField("حجم")
    unit_price = models.PositiveIntegerField("قیمت واحد")
    quantity = models.PositiveSmallIntegerField("تعداد")

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
