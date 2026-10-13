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
STAFF_OTP = "staff_otp"
LOW_STOCK = "low_stock"
BACK_IN_STOCK = "back_in_stock"
CART_REMINDER = "cart_reminder"
CAMPAIGN = "campaign"
GIFT_CARD = "gift_card"
RETURN_UPDATE = "return_update"
PRICE_DROP = "price_drop"
REFERRAL_REWARD = "referral_reward"

EVENT_CHOICES = [
    (ORDER_PLACED, "ثبت سفارش"),
    (ORDER_PAID, "پرداخت سفارش"),
    (ORDER_PROCESSING, "در حال آماده‌سازی"),
    (ORDER_SHIPPED, "ارسال سفارش"),
    (ORDER_DELIVERED, "تحویل سفارش"),
    (ORDER_CANCELLED, "لغو سفارش"),
    (OTP, "کد ورود یک‌بارمصرف"),
    (STAFF_OTP, "کد ورود دومرحله‌ای کارکنان"),
    (LOW_STOCK, "موجودی کم"),
    (BACK_IN_STOCK, "موجود شد خبرم کن"),
    (CART_REMINDER, "یادآوری سبد خرید رهاشده"),
    (CAMPAIGN, "پیامک گروهی به مشتریان"),
    (GIFT_CARD, "ارسال کارت هدیه"),
    (RETURN_UPDATE, "مرجوعی و لغو بخشی"),
    (PRICE_DROP, "کاهش قیمت علاقه‌مندی"),
    (REFERRAL_REWARD, "پاداش معرفی دوست"),
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
STOCK_VARS = ("store", "product", "size", "stock", "product_url")
NON_ORDER_EVENTS = {
    OTP: ("store", "code", "minutes"),
    STAFF_OTP: ("store", "code", "minutes"),
    LOW_STOCK: STOCK_VARS,
    BACK_IN_STOCK: STOCK_VARS,
    CART_REMINDER: ("store", "name", "items", "total", "cart_url"),
    CAMPAIGN: ("store", "name", "code", "percent", "message", "shop_url"),
    GIFT_CARD: ("store", "name", "code", "amount", "sender", "message", "expires", "shop_url"),
    RETURN_UPDATE: ("store", "name", "number", "kind", "status", "amount", "order_url"),
    PRICE_DROP: ("store", "name", "product", "old_price", "new_price", "percent", "product_url"),
    REFERRAL_REWARD: ("store", "name", "friend", "reward", "shop_url"),
}
EVENT_VARS = {event: ORDER_VARS for event, _ in EVENT_CHOICES if event not in NON_ORDER_EVENTS}
EVENT_VARS.update(NON_ORDER_EVENTS)


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
    DefaultRule(STAFF_OTP, SMS, STAFF, True, "کد ورود پنل مدیریت {store}: {code}\nاعتبار: {minutes} دقیقه. این کد را به کسی ندهید."),
    DefaultRule(LOW_STOCK, SMS, STAFF, True, "موجودی «{product}» ({size}) به {stock} عدد رسید."),
    DefaultRule(LOW_STOCK, EMAIL, STAFF, True, "موجودی «{product}» ({size}) به {stock} عدد رسید.\n{product_url}",
                subject="موجودی کم: {product} ({size})"),
    DefaultRule(BACK_IN_STOCK, SMS, CUSTOMER, True, "«{product}» ({size}) در {store} دوباره موجود شد:\n{product_url}"),
    DefaultRule(CART_REMINDER, SMS, CUSTOMER, True,
                "{name} عزیز، {items} در سبد خرید شما در {store} منتظر است. ادامه خرید:\n{cart_url}"),
    DefaultRule(CAMPAIGN, SMS, CUSTOMER, True, "{message}"),
    DefaultRule(RETURN_UPDATE, SMS, CUSTOMER, True,
                "{name} عزیز، {kind} سفارش {number}: {status}. مبلغ: {amount}\n{order_url}"),
    DefaultRule(RETURN_UPDATE, SMS, STAFF, True, "{kind} جدید برای سفارش {number} — {amount}"),
    DefaultRule(PRICE_DROP, SMS, CUSTOMER, True,
                "{name} عزیز، قیمت «{product}» در {store} {percent}٪ کم شد: {new_price} (قبلاً {old_price})\n{product_url}"),
    DefaultRule(PRICE_DROP, EMAIL, CUSTOMER, True,
                "{name} عزیز، قیمت «{product}» که در علاقه‌مندی‌های شماست {percent}٪ کم شد.\n"
                "قیمت جدید: {new_price} (قبلاً {old_price})\n{product_url}",
                subject="کاهش قیمت: {product}"),
    DefaultRule(REFERRAL_REWARD, SMS, CUSTOMER, True,
                "{name} عزیز، دوستتان {friend} اولین خریدش را از {store} تحویل گرفت. پاداش شما: {reward}\n{shop_url}"),
    DefaultRule(GIFT_CARD, SMS, CUSTOMER, True,
                "کارت هدیه {amount} از طرف {sender} در {store}\nکد: {code}\n{message}\n{shop_url}"),
]
