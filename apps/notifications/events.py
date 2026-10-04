"""رویدادهای اطلاع‌رسانی، متغیرهای مجاز متن پیام‌ها و پیش‌فرض‌ها."""

import string
from dataclasses import dataclass

from django.core.exceptions import ValidationError

ORDER_PLACED = "order_placed"
ORDER_PAID = "order_paid"
ORDER_PROCESSING = "order_processing"
ORDER_SHIPPED = "order_shipped"
ORDER_DELIVERED = "order_delivered"
ORDER_CANCELLED = "order_cancelled"
OTP = "otp"

EVENT_CHOICES = [
    (ORDER_PLACED, "ثبت سفارش"),
    (ORDER_PAID, "پرداخت سفارش"),
    (ORDER_PROCESSING, "در حال آماده‌سازی"),
    (ORDER_SHIPPED, "ارسال سفارش"),
    (ORDER_DELIVERED, "تحویل سفارش"),
    (ORDER_CANCELLED, "لغو سفارش"),
    (OTP, "کد ورود یک‌بارمصرف"),
]

# وضعیت جدید سفارش ← رویداد
STATUS_EVENTS = {
    "paid": ORDER_PAID,
    "processing": ORDER_PROCESSING,
    "shipped": ORDER_SHIPPED,
    "delivered": ORDER_DELIVERED,
    "cancelled": ORDER_CANCELLED,
}

ORDER_VARS = ("store", "name", "number", "total", "status", "payment_method", "shipping_method",
              "tracking_code", "tracking_url", "order_url", "phone")
EVENT_VARS = {event: ORDER_VARS for event, _ in EVENT_CHOICES if event != OTP}
EVENT_VARS[OTP] = ("store", "code", "minutes")


def placeholders(text):
    return [name for _, name, _, _ in string.Formatter().parse(text or "") if name is not None]


def validate_text(event, text):
    allowed = EVENT_VARS.get(event, ())
    try:
        names = placeholders(text)
    except ValueError as exc:
        raise ValidationError("آکولاد باز و بسته { } متن نامعتبر است.") from exc
    unknown = [n for n in names if n not in allowed]
    if unknown:
        raise ValidationError(
            f"متغیر ناشناخته: {', '.join('{' + n + '}' for n in unknown)}. "
            f"متغیرهای مجاز: {' '.join('{' + n + '}' for n in allowed)}"
        )


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def render_text(text, context):
    return string.Formatter().vformat(text or "", (), _SafeDict(context)).strip()


@dataclass(frozen=True)
class DefaultRule:
    event: str
    channel: str
    audience: str
    is_active: bool
    text: str = ""
    subject: str = ""


SMS, EMAIL = "sms", "email"
CUSTOMER, STAFF = "customer", "staff"

DEFAULT_RULES = [
    DefaultRule(ORDER_PLACED, SMS, CUSTOMER, True,
                "{name} عزیز، سفارش {number} در {store} ثبت شد. مبلغ: {total}\n{order_url}"),
    DefaultRule(ORDER_PLACED, EMAIL, CUSTOMER, True, subject="سفارش {number} ثبت شد"),
    DefaultRule(ORDER_PLACED, SMS, STAFF, True, "سفارش جدید {number} — {total} — {payment_method}"),
    DefaultRule(ORDER_PLACED, EMAIL, STAFF, True, subject="سفارش جدید {number}"),
    DefaultRule(ORDER_PAID, SMS, CUSTOMER, True, "پرداخت سفارش {number} با موفقیت انجام شد. از خرید شما سپاسگزاریم."),
    DefaultRule(ORDER_PAID, EMAIL, CUSTOMER, True, subject="پرداخت سفارش {number} تأیید شد"),
    DefaultRule(ORDER_PROCESSING, SMS, CUSTOMER, False, "سفارش {number} در حال آماده‌سازی است."),
    DefaultRule(ORDER_SHIPPED, SMS, CUSTOMER, True,
                "سفارش {number} با {shipping_method} ارسال شد. کد رهگیری: {tracking_code}\n{tracking_url}"),
    DefaultRule(ORDER_SHIPPED, EMAIL, CUSTOMER, True, subject="سفارش {number} ارسال شد"),
    DefaultRule(ORDER_DELIVERED, SMS, CUSTOMER, False, "سفارش {number} تحویل شد. امیدواریم از خرید خود لذت ببرید."),
    DefaultRule(ORDER_CANCELLED, SMS, CUSTOMER, True, "سفارش {number} لغو شد. برای پیگیری با ما تماس بگیرید."),
    DefaultRule(ORDER_CANCELLED, EMAIL, CUSTOMER, True, subject="سفارش {number} لغو شد"),
    DefaultRule(OTP, SMS, CUSTOMER, True, "کد ورود شما به {store}: {code}\nاین کد تا {minutes} دقیقه معتبر است."),
]
