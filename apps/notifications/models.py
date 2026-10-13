from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.validators import iran_mobile_validator

from . import events as E


def _split(value):
    return [item.strip() for item in (value or "").replace("،", ",").split(",") if item.strip()]


class NotificationSettings(models.Model):
    store = models.OneToOneField("core.Store", on_delete=models.CASCADE, related_name="notification_settings",
                                 verbose_name="فروشگاه")
    sms_enabled = models.BooleanField("ارسال پیامک", default=True,
                                      help_text="سرویس پیامک با SMS_PROVIDER و SMS_API_KEY در .env تنظیم می‌شود")
    email_enabled = models.BooleanField("ارسال ایمیل", default=True)
    staff_phones = models.CharField("موبایل مدیران", max_length=200, blank=True,
                                    help_text="برای پیامک «سفارش جدید»؛ چند شماره را با کاما جدا کنید")
    staff_emails = models.CharField("ایمیل مدیران", max_length=300, blank=True,
                                    help_text="برای ایمیل «سفارش جدید»؛ چند ایمیل را با کاما جدا کنید")
    cart_reminder_enabled = models.BooleanField(
        "یادآوری سبد رهاشده", default=True,
        help_text="به مشتری واردشده‌ای که سبدش را پر کرده ولی سفارش نداده، یک پیامک یادآوری می‌رود",
    )
    cart_reminder_hours = models.PositiveSmallIntegerField(
        "یادآوری پس از (ساعت)", default=3, help_text="چند ساعت بعد از آخرین تغییر سبد",
    )
    price_drop_enabled = models.BooleanField(
        "خبر کاهش قیمت علاقه‌مندی‌ها", default=True,
        help_text="وقتی قیمت محصولی در علاقه‌مندی‌های مشتری پایین بیاید، به او پیامک/ایمیل می‌رود",
    )
    price_drop_percent = models.PositiveSmallIntegerField(
        "حداقل کاهش (درصد)", default=5, validators=[MinValueValidator(1), MaxValueValidator(90)],
        help_text="فقط کاهش‌های دست‌کم این‌قدر اطلاع داده می‌شوند",
    )
    staff_2fa_enabled = models.BooleanField(
        "ورود دومرحله‌ای کارکنان", default=False,
        help_text="کارکنان بعد از رمز عبور، کد پیامکی به موبایل حسابشان می‌گیرند (موبایل کارمند باید ثبت شده باشد)",
    )
    otp_login_enabled = models.BooleanField(
        "ورود با کد پیامکی", default=False,
        help_text="مشتری با شماره موبایل و کد یک‌بارمصرف وارد می‌شود (نیاز به سرویس پیامک فعال)",
    )

    class Meta:
        verbose_name = "تنظیمات اطلاع‌رسانی"
        verbose_name_plural = "تنظیمات اطلاع‌رسانی"

    def __str__(self):
        return f"اطلاع‌رسانی {self.store}"

    @property
    def staff_phone_list(self):
        return _split(self.staff_phones)

    @property
    def staff_email_list(self):
        return _split(self.staff_emails)

    def clean(self):
        for phone in self.staff_phone_list:
            iran_mobile_validator(phone)
        for email in self.staff_email_list:
            if "@" not in email:
                raise ValidationError({"staff_emails": f"ایمیل نامعتبر: {email}"})


class NotificationRule(models.Model):
    """یک پیام: رویداد × کانال × گیرنده؛ متن و الگوی پیامک قابل ویرایش در پنل مدیریت."""

    CHANNELS = [(E.SMS, "پیامک"), (E.EMAIL, "ایمیل")]
    AUDIENCES = [(E.CUSTOMER, "مشتری"), (E.STAFF, "مدیران فروشگاه")]

    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه")
    event = models.CharField("رویداد", max_length=30, choices=E.EVENT_CHOICES)
    channel = models.CharField("کانال", max_length=10, choices=CHANNELS)
    audience = models.CharField("گیرنده", max_length=10, choices=AUDIENCES, default=E.CUSTOMER)
    is_active = models.BooleanField("فعال", default=True)
    text = models.TextField(
        "متن پیامک", blank=True,
        help_text="برای پیامک متنی. متغیرها: {store} {name} {number} {total} {status} {payment_method} "
                  "{shipping_method} {tracking_code} {tracking_url} {order_url} {phone} — کد ورود: {code} {minutes}",
    )
    sms_template = models.CharField(
        "کد الگوی پیامک (Pattern)", max_length=60, blank=True,
        help_text="اگر پر باشد به‌جای متن، الگوی تأییدشده پنل پیامک ارسال می‌شود (کاوه‌نگار: نام الگو؛ SMS.ir: شناسه قالب)",
    )
    template_params = models.CharField(
        "متغیرهای الگو", max_length=200, blank=True,
        help_text="به ترتیب الگو، با کاما؛ مثلاً number,total یا برای کد ورود: code",
    )
    subject = models.CharField("موضوع ایمیل", max_length=150, blank=True)

    class Meta:
        ordering = ["event", "audience", "channel"]
        verbose_name = "پیام"
        verbose_name_plural = "پیام‌ها (متن و الگوها)"
        constraints = [
            models.UniqueConstraint(fields=["store", "event", "channel", "audience"], name="notifications_unique_rule"),
        ]

    def __str__(self):
        return f"{self.get_event_display()} · {self.get_channel_display()} · {self.get_audience_display()}"

    @property
    def param_names(self):
        return _split(self.template_params)

    def clean(self):
        errors = {}
        for field in ("text", "subject"):
            try:
                E.validate_text(self.event, getattr(self, field))
            except ValidationError as exc:
                errors[field] = exc.messages
        unknown = [p for p in self.param_names if p not in E.EVENT_VARS.get(self.event, ())]
        if unknown:
            errors["template_params"] = f"متغیر ناشناخته: {', '.join(unknown)}"
        elif self.sms_template and not self.param_names:
            errors["template_params"] = "متغیرهای الگو را به ترتیب وارد کنید."
        if errors:
            raise ValidationError(errors)


class NotificationLog(models.Model):
    SENT, FAILED, SKIPPED = "sent", "failed", "skipped"
    STATUSES = [(SENT, "ارسال شد"), (FAILED, "ناموفق"), (SKIPPED, "ارسال نشد")]

    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه")
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                              verbose_name="سفارش")
    campaign = models.ForeignKey("Campaign", on_delete=models.SET_NULL, null=True, blank=True, related_name="logs",
                                 verbose_name="پیامک گروهی")
    event = models.CharField("رویداد", max_length=30, choices=E.EVENT_CHOICES)
    channel = models.CharField("کانال", max_length=10, choices=NotificationRule.CHANNELS)
    recipient = models.CharField("گیرنده", max_length=254)
    status = models.CharField("وضعیت", max_length=10, choices=STATUSES)
    provider = models.CharField("سرویس", max_length=30, blank=True)
    message_id = models.CharField("شناسه پیام", max_length=100, blank=True)
    body = models.TextField("متن", blank=True)
    error = models.CharField("خطا", max_length=300, blank=True)
    attempts = models.PositiveSmallIntegerField("تعداد تلاش", default=1)
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("آخرین تلاش", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پیام ارسالی"
        verbose_name_plural = "گزارش پیام‌های ارسالی"
        constraints = [
            # هر پیام سفارش فقط یک بار (اجرای دوباره task با acks_late پیام تکراری نمی‌فرستد)
            models.UniqueConstraint(fields=["order", "event", "channel", "recipient"],
                                    condition=models.Q(order__isnull=False), name="notifications_once_per_order"),
        ]

    def __str__(self):
        return f"{self.get_event_display()} → {self.recipient}"


class Campaign(models.Model):
    """پیامک گروهی به یک گروه مشتری (با کد تخفیف اختیاری)."""

    SENDING, DONE = "sending", "done"
    STATUSES = [("sending", "در حال ارسال"), ("done", "ارسال شد")]

    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, related_name="+", verbose_name="فروشگاه")
    name = models.CharField("عنوان", max_length=100)
    message = models.TextField("متن پیامک", max_length=600)
    audience = models.CharField("گروه مخاطب", max_length=200, blank=True)
    recipients = models.JSONField("گیرندگان", default=list, help_text="[[موبایل، نام]، …]")
    coupon_code = models.CharField("کد تخفیف", max_length=30, blank=True)
    status = models.CharField("وضعیت", max_length=10, choices=STATUSES, default="sending")
    sent = models.PositiveIntegerField("ارسال موفق", default=0)
    failed = models.PositiveIntegerField("ناموفق", default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="کاربر")
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پیامک گروهی"
        verbose_name_plural = "پیامک‌های گروهی"

    def __str__(self):
        return self.name

    @property
    def total(self):
        return len(self.recipients)
