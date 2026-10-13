"""تنظیمات هدر و فوتر فروشگاه (ThemeSettings.header / ThemeSettings.footer).

مثل بخش‌های صفحه، schema هر کدام یک فرم Django است: اعتبارسنجی، مقادیر پیش‌فرض و فرم ویرایش سازنده پوسته
همه از همین فرم‌ها ساخته می‌شوند. مقادیر پیش‌فرض همان طراحی فعلی است.
"""

import logging

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from apps.core.schema import ListOfDictsField, validate_link

log = logging.getLogger(__name__)

LINK_LABELS = {"label": "عنوان", "url": "پیوند"}


def _links(label, initial, max_items=8):
    return ListOfDictsField(label=label, keys=("label", "url"), max_items=max_items, initial=initial,
                            labels=LINK_LABELS, validators_by_key={"url": [validate_link]})


def _text(label, initial, max_length=200):
    return forms.CharField(label=label, initial=initial, required=False, max_length=max_length)


class HeaderForm(forms.Form):
    menu = _links("منوی اصلی", [
        {"label": "خانه", "url": "/"},
        {"label": "فروشگاه", "url": "/shop/"},
        {"label": "کالکشن‌ها", "url": "/collections/"},
        {"label": "مجله", "url": "/blog/"},
        {"label": "درباره ما", "url": "/about/"},
        {"label": "تماس با ما", "url": "/contact/"},
    ])
    logo_height = forms.IntegerField(label="ارتفاع لوگو (px)", initial=40, min_value=24, max_value=80)
    monogram = forms.CharField(
        label="حرف نماد (برای فاوآیکون پیش‌فرض)", initial="", required=False, max_length=1,
        validators=[RegexValidator(r"^[^<>&\"'\s]?$", "یک حرف")],
    )
    show_search = forms.BooleanField(label="نمایش جستجو", initial=True, required=False)
    show_account = forms.BooleanField(label="نمایش حساب کاربری", initial=True, required=False)
    sticky = forms.BooleanField(label="هدر چسبان (هنگام اسکرول ثابت بماند)", initial=True, required=False)


class FooterForm(forms.Form):
    about = _text("متن معرفی (بعد از شعار)", "رایحه‌هایی برای ماندگاری در خاطره‌ها.", 300)
    show_social = forms.BooleanField(label="نمایش شبکه‌های اجتماعی", initial=True, required=False)
    links_title = _text("عنوان ستون اول", "دسترسی سریع", 60)
    links = _links("پیوندهای ستون اول", [
        {"label": "فروشگاه", "url": "/shop/"},
        {"label": "کالکشن‌ها", "url": "/collections/"},
        {"label": "مجله", "url": "/blog/"},
        {"label": "باکس‌های هدیه", "url": "/gift-boxes/"},
        {"label": "نمونه و باکس تست", "url": "/samples/"},
        {"label": "درباره ما", "url": "/about/"},
    ])
    service_title = _text("عنوان ستون دوم", "خدمات مشتریان", 60)
    service_links = _links("پیوندهای ستون دوم", [
        {"label": "سوالات متداول", "url": "/contact/"},
        {"label": "بازگشت و تعویض", "url": "/contact/"},
        {"label": "شرایط ارسال", "url": "/contact/"},
        {"label": "پیگیری سفارش", "url": "/account/"},
    ])
    contact_title = _text("عنوان ستون تماس", "تماس با ما", 60)
    hours = _text("ساعات پاسخگویی", "شنبه تا پنجشنبه، ۱۰ تا ۲۱", 120)
    copyright = _text("متن کپی‌رایت", "تمامی حقوق محفوظ است.", 200)


FORMS = {"header": HeaderForm, "footer": FooterForm}


def defaults(part):
    form = FORMS[part]()
    return {name: field.initial for name, field in form.fields.items()}


def clean(part, data):
    """اعتبارسنجی تنظیمات هدر/فوتر؛ کلیدهای ناموجود از پیش‌فرض پر می‌شوند."""
    if not isinstance(data or {}, dict):
        raise ValidationError("باید یک شیء JSON باشد.")
    unknown = set(data or {}) - set(FORMS[part].base_fields)
    if unknown:
        raise ValidationError(f"کلید ناشناخته: {', '.join(sorted(map(str, unknown)))}")
    form = FORMS[part](data={**defaults(part), **(data or {})})
    if not form.is_valid():
        raise ValidationError({k: v for k, v in form.errors.items()})
    return form.cleaned_data


def resolve(part, theme_settings):
    """تنظیمات نهایی برای نمایش. داده خراب فروشگاه را از کار نمی‌اندازد (برگشت به پیش‌فرض)."""
    data = getattr(theme_settings, part, None) or {}
    try:
        return clean(part, data)
    except ValidationError:
        log.warning("Invalid %s settings for ThemeSettings %s; using defaults", part, getattr(theme_settings, "pk", None))
        return clean(part, {})


# مسیرهایی که زیرمجموعه یک پیوند منو حساب می‌شوند (صفحه محصول ← «فروشگاه»)
NAV_ALIASES = {"/shop/": ("/product/",)}


def is_active_link(url, path):
    if not url or not url.startswith("/"):
        return False
    url = url.split("?", 1)[0].split("#", 1)[0]
    if url == "/":
        return path == "/"
    return path.startswith(url) or any(path.startswith(alias) for alias in NAV_ALIASES.get(url, ()))
