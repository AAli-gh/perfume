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

    class Packaging(models.TextChoices):
        NONE = "none", "بسته‌بندی معمولی"
        IN_BOX = "in_box", "عطرها داخل باکس هدیه چیده شوند"
        SEPARATE = "separate", "باکس هدیه جدا ارسال شود (بدون چیدن)"
        CUSTOM = "custom", "توضیح می‌دهم چطور بسته‌بندی شود"

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
    total = models.PositiveIntegerField("مبلغ نهایی", default=0, help_text="مبلغ قابل پرداخت (بعد از کارت هدیه و امتیاز)")
    coupon_code = models.CharField("کد تخفیف", max_length=30, blank=True)
    gift_card_code = models.CharField("کارت هدیه", max_length=20, blank=True)
    gift_card_amount = models.PositiveIntegerField("پرداخت با کارت هدیه", default=0)
    points_used = models.PositiveIntegerField("امتیاز خرج‌شده", default=0)
    points_amount = models.PositiveIntegerField("تخفیف امتیاز باشگاه", default=0)
    gift_cards_issued = models.BooleanField("کارت هدیه خریداری‌شده صادر شد", default=False, editable=False)

    shipping_method = models.ForeignKey(
        "shipping.ShippingMethod", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="روش ارسال",
    )
    shipping_method_name = models.CharField("عنوان روش ارسال", max_length=80, blank=True)
    tracking_code = models.CharField(
        "کد رهگیری مرسوله", max_length=60, blank=True,
        help_text="پیش از تغییر وضعیت به «ارسال شده» وارد کنید تا در پیامک و ایمیل مشتری بیاید",
    )
    shipped_at = models.DateTimeField("زمان ارسال", null=True, blank=True)

    packaging = models.CharField("بسته‌بندی", max_length=10, choices=Packaging.choices, default=Packaging.NONE)
    packaging_note = models.TextField("توضیح بسته‌بندی", max_length=500, blank=True)
    gift_message = models.TextField("پیام کارت هدیه", max_length=300, blank=True)
    gift_from = models.CharField("از طرف (روی کارت)", max_length=80, blank=True)
    hide_prices = models.BooleanField("فاکتور قیمت داخل بسته نباشد", default=False)

    reserved_until = models.DateTimeField(
        "مهلت پرداخت", null=True, blank=True, db_index=True,
        help_text="سفارش آنلاین پرداخت‌نشده بعد از این زمان لغو و موجودی آزاد می‌شود",
    )
    inventory_released = models.BooleanField("موجودی آزاد شده", default=False, editable=False)

    paid_at = models.DateTimeField("زمان پرداخت", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"

    @property
    def is_gift(self):
        return self.packaging != self.Packaging.NONE or bool(self.gift_message)

    @property
    def tracking_url(self):
        if not self.tracking_code or self.shipping_method is None:
            return ""
        return self.shipping_method.tracking_url(self.tracking_code)

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


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="سفارش")
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کالا"
    )
    product_name = models.CharField("نام محصول", max_length=150)
    size_ml = models.PositiveSmallIntegerField("حجم")
    unit_price = models.PositiveIntegerField("قیمت واحد")
    quantity = models.PositiveSmallIntegerField("تعداد")
    returned_quantity = models.PositiveSmallIntegerField(
        "مرجوع/لغوشده", default=0, editable=False, help_text="تعدادی که لغو بخشی یا مرجوعی (دریافت‌شده) شده است")

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def returnable_quantity(self):
        return self.quantity - self.returned_quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history", verbose_name="سفارش")
    from_status = models.CharField("از وضعیت", max_length=20, choices=Order.Status.choices)
    to_status = models.CharField("به وضعیت", max_length=20, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="توسط"
    )
    note = models.CharField("توضیح", max_length=200, blank=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "تاریخچه وضعیت"
        verbose_name_plural = "تاریخچه وضعیت"

    def __str__(self):
        return f"{self.order}: {self.get_from_status_display()} ← {self.get_to_status_display()}"


class CustomerProfile(StoreOwned):
    """یادداشت داخلی و برچسب‌های یک مشتری (بر اساس موبایل؛ برای مهمان‌ها هم کار می‌کند)."""

    phone = models.CharField("موبایل", max_length=11, validators=[phone_validator])
    tags = models.CharField("برچسب‌ها", max_length=200, blank=True, help_text="با کاما جدا کنید؛ مثلاً همکار، عمده")
    note = models.TextField("یادداشت داخلی", blank=True, help_text="فقط کارکنان می‌بینند")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="آخرین ویرایش توسط")
    updated_at = models.DateTimeField("آخرین ویرایش", auto_now=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        verbose_name = "پرونده مشتری"
        verbose_name_plural = "پرونده مشتریان"
        constraints = [models.UniqueConstraint(fields=["store", "phone"], name="orders_customer_profile_unique")]

    def __str__(self):
        return self.phone

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.replace("،", ",").split(",") if t.strip()]


class ReturnRequest(models.Model):
    """مرجوعی (پس از ارسال) یا لغو بخشی از سفارش (پیش از ارسال)."""

    class Kind(models.TextChoices):
        RETURN = "return", "مرجوعی"
        CANCEL = "cancel", "لغو بخشی از سفارش"

    class Status(models.TextChoices):
        REQUESTED = "requested", "در انتظار بررسی"
        APPROVED = "approved", "تأییدشده؛ منتظر دریافت کالا"
        RECEIVED = "received", "کالا دریافت شد؛ منتظر بازپرداخت"
        REFUNDED = "refunded", "بازپرداخت شد"
        REJECTED = "rejected", "ردشده"
        CLOSED = "closed", "انجام شد"

    class Reason(models.TextChoices):
        DAMAGED = "damaged", "آسیب‌دیده یا شکسته"
        WRONG = "wrong", "کالای اشتباه ارسال شده"
        NOT_AS_DESCRIBED = "not_as_described", "با توضیحات مطابقت ندارد"
        CHANGED_MIND = "changed_mind", "منصرف شدم"
        OUT_OF_STOCK = "out_of_stock", "ناموجودی در انبار (لغو توسط فروشگاه)"
        OTHER = "other", "سایر"

    class RefundMethod(models.TextChoices):
        CARD = "card", "واریز به کارت مشتری"
        GATEWAY = "gateway", "برگشت از درگاه پرداخت"
        CASH = "cash", "نقدی / هنگام تحویل کسر شد"
        CREDIT = "credit", "اعتبار خرید (کارت هدیه)"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="returns", verbose_name="سفارش")
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.RETURN)
    status = models.CharField("وضعیت", max_length=12, choices=Status.choices, default=Status.REQUESTED)
    reason = models.CharField("علت", max_length=20, choices=Reason.choices)
    description = models.TextField("توضیح مشتری", max_length=1000, blank=True)
    by_customer = models.BooleanField("ثبت توسط مشتری", default=False)
    refund_amount = models.PositiveIntegerField("مبلغ بازپرداخت", default=0)
    refund_method = models.CharField("روش بازپرداخت", max_length=10, choices=RefundMethod.choices, blank=True)
    refund_reference = models.CharField("کد پیگیری بازپرداخت", max_length=100, blank=True)
    staff_note = models.TextField("یادداشت کارکنان", blank=True)
    restocked = models.BooleanField("به انبار برگشت", default=False, editable=False)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="رسیدگی توسط")
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)
    refunded_at = models.DateTimeField("زمان بازپرداخت", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "مرجوعی / لغو بخشی"
        verbose_name_plural = "مرجوعی‌ها و لغوهای بخشی"

    def __str__(self):
        return f"{self.get_kind_display()} {self.order.number}"

    @property
    def is_open(self):
        return self.status in (self.Status.REQUESTED, self.Status.APPROVED, self.Status.RECEIVED)


class ReturnItem(models.Model):
    request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name="items", verbose_name="درخواست")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="+", verbose_name="قلم سفارش")
    quantity = models.PositiveSmallIntegerField("تعداد")

    class Meta:
        verbose_name = "قلم مرجوعی"
        verbose_name_plural = "اقلام مرجوعی"

    def __str__(self):
        return f"{self.order_item.product_name} × {self.quantity}"
