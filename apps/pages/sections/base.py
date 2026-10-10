"""پایه بخش‌های صفحه (Homepage Builder).

هر نوع بخش:
- key / label / icon: شناسه و نام نمایشی در سازنده صفحه
- form_class: schema تنظیمات (فرم Django) — اعتبارسنجی و فرم ویرایش از همین ساخته می‌شود
- template: قالب در لایه پوسته (themes/<theme>/templates/sections/<key>.html) — هر پوسته می‌تواند override کند
- get_context(): داده‌ها را فقط از selectorهای هسته می‌گیرد (منطق در بخش‌ها نیست)
"""

import re

from django import forms
from django.core.exceptions import ValidationError
from django.templatetags.static import static

from apps.core.schema import SAFE_URL, LinkField, validate_link  # noqa: F401 — بازصادر برای سازگاری

STATIC_IMAGE = re.compile(r"^[a-z0-9][a-z0-9/_.-]*\.(jpg|jpeg|png|webp|svg)$")


def validate_static_image(value):
    if value and (".." in value or not STATIC_IMAGE.match(value)):
        raise ValidationError("مسیر تصویر پوسته نامعتبر است.")


class SectionForm(forms.Form):
    """پایه فرم تنظیمات بخش‌ها."""


class SectionType:
    key = ""
    label = ""
    description = ""
    icon = "grid"
    form_class = SectionForm
    full_bleed = False  # بخش تمام‌عرض (مثل هیرو) فاصله عمودی معمول را نمی‌گیرد
    uses_image = False
    hidden_hint = ""  # وقتی is_visible نادرست است، در استودیو به مدیر گفته می‌شود چرا بخش در سایت دیده نمی‌شود
    audience_note = ""  # بخش‌هایی که برای هر بازدیدکننده متفاوت‌اند

    @property
    def template(self):
        return f"sections/{self.key}.html"

    def defaults(self):
        form = self.form_class()
        return {name: field.initial for name, field in form.fields.items() if field.initial is not None}

    def clean_settings(self, data):
        """اعتبارسنجی تنظیمات؛ مقادیر ناموجود از پیش‌فرض پر می‌شوند."""
        merged = {**self.defaults(), **(data or {})}
        form = self.form_class(data=merged)
        if not form.is_valid():
            raise ValidationError({k: v for k, v in form.errors.items()})
        return form.cleaned_data

    def image_url(self, section, settings):
        if section is not None and section.image:
            return section.image.url
        path = settings.get("image_static")
        return static(path) if path else ""

    def get_context(self, settings, *, request, section=None):
        return dict(settings)

    def is_visible(self, context):
        """بخشی که داده‌ای برای نمایش ندارد (مثلاً مجله بدون مقاله) پنهان می‌شود."""
        return True
