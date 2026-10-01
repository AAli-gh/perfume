"""فیلترهای قالب: اعداد فارسی، قیمت تومان، تاریخ شمسی و ستاره امتیاز."""

import re

import jdatetime
from django import template
from django.utils import timezone
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def fa(value):
    """تبدیل ارقام لاتین به فارسی."""
    if value is None:
        return ""
    return str(value).translate(FA_DIGITS)


@register.filter
def fa_int(value):
    """عدد با جداکننده هزارگان و ارقام فارسی."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return value
    return f"{n:,}".replace(",", "٬").translate(FA_DIGITS)


def _currency_label():
    from apps.core.stores import get_current_store

    try:
        return get_current_store().config.currency_label or "تومان"
    except Exception:  # فروشگاه یا تنظیمات هنوز ساخته نشده (مثلاً حین migration)
        return "تومان"


@register.filter
def toman(value):
    """مبلغ با جداکننده و ارقام فارسی + واحد پول فروشگاه جاری (پیش‌فرض: تومان)."""
    return f"{fa_int(value or 0)} {_currency_label()}"


money = register.filter("money", toman)


@register.filter
def jdate(value, fmt="%d %B %Y"):
    """نمایش تاریخ به تقویم شمسی."""
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    jd = jdatetime.datetime.fromgregorian(datetime=value, locale="fa_IR")
    return jd.strftime(fmt).translate(FA_DIGITS)


@register.simple_tag
def stars(rating, count=None):
    rating = rating or 0
    full = int(round(rating))
    label = f"امتیاز {fa(round(rating, 1))} از ۵"
    extra = format_html('<small class="ms-1.5 text-xs text-muted">({})</small>', fa(count)) if count is not None else ""
    return format_html(
        '<span class="stars" aria-label="{}">{}{}</span>', label, "★" * full + "☆" * (5 - full), extra
    )


@register.filter
def br_only(text):
    """escape کامل متن؛ فقط شکست خط <br> مجاز است (جایگزین امن |safe در عنوان‌ها)."""
    escaped = conditional_escape(text or "")
    return mark_safe(re.sub(r"&lt;br\s*/?&gt;", "<br>", escaped))


@register.filter
def article(text):
    """متن ساده مقاله → HTML: پاراگراف‌ها با خط خالی جدا شده‌اند، خطوط ## تیتر هستند."""
    parts = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            parts.append(f"<h2>{conditional_escape(block[3:])}</h2>")
        else:
            parts.append(f"<p>{conditional_escape(block).replace(chr(10), '<br>')}</p>")
    return mark_safe("\n".join(parts))



ICONS = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    "cart": '<path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2"/><circle cx="10" cy="20.5" r="1"/><circle cx="17" cy="20.5" r="1"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "chev-left": '<path d="m15 6-6 6 6 6"/>',
    "chev-right": '<path d="m9 6 6 6-6 6"/>',
    "grid": '<rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r=".8"/><circle cx="4.5" cy="12" r=".8"/><circle cx="4.5" cy="18" r=".8"/>',
    "filter": '<path d="M4 5h16l-6 8v5l-4 2v-7z"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m3 7 9 6 9-6"/>',
    "pin": '<path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    "diamond": '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20M9 3l3 18 3-18"/>',
    "crown": '<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 10H5z"/><path d="M5 21h14"/>',
    "flame": '<path d="M12 3c1 4 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-3.5 2-5.5 1 1.5 2 2 2.5 3.5C13 8 12 5 12 3z"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="M12 3v18"/>',
    "shield-check": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "truck": '<path d="M2 6h12v10H2zM14 10h4l3 3v3h-7"/><circle cx="6" cy="18" r="1.8"/><circle cx="17" cy="18" r="1.8"/>',
    "gift": '<rect x="3" y="9" width="18" height="12"/><path d="M3 13h18M12 9v12M12 9C9 9 7 4 10 4s2 5 2 5 0-5 3-5 1 5-3 5"/>',
    "headset": '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="3" y="14" width="4" height="6" rx="1"/><rect x="17" y="14" width="4" height="6" rx="1"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/>',
    "bag": '<path d="M5 8h14l-1 13H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    "instagram": '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".6"/>',
    "telegram": '<path d="M21 4 3 11l6 2 2 6 3-4 5 4z"/><path d="m9 13 9-7"/>',
    "whatsapp": '<path d="M4 20l1.3-4A8 8 0 1 1 8 18.7z"/><path d="M9 9c0 3 3 6 6 6l1-1.5-2-1-1 1c-1-.5-2-1.5-2.5-2.5l1-1-1-2z"/>',
    "x": '<path d="M4 4l16 16M20 4 4 20"/>',
    "logout": '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
}


@register.simple_tag
def icon(name, cls=""):
    return format_html(
        '<svg class="icon {}" viewBox="0 0 24 24" aria-hidden="true">{}</svg>', cls, mark_safe(ICONS.get(name, ""))
    )
