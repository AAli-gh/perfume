"""تاریخ شمسی در فرم‌ها: ورود «۱۴۰۵/۰۷/۲۰ ۱۴:۳۰» و ذخیره datetime میلادی (aware).

- JalaliDateTimeField / JalaliDateField: فیلد فرم با ارقام فارسی یا لاتین و جداکننده / یا -.
- JalaliAdminMixin: در پنل مدیریت همه فیلدهای تاریخ را شمسی می‌کند (با تقویم انتخاب تاریخ js/jalali-picker.js).
"""

import datetime
import re

import jdatetime
from django import forms
from django.db import models
from django.utils import timezone

from .forms import en_digits

_PATTERN = re.compile(r"^\s*(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?:[\sT،,]+(\d{1,2})(?::(\d{1,2}))?)?\s*$")
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_jalali_text(value, with_time=True):
    if not value:
        return ""
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        jd = jdatetime.datetime.fromgregorian(datetime=value)
        return jd.strftime("%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d").translate(FA_DIGITS)
    return jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d").translate(FA_DIGITS)


def parse_jalali(text, *, end_of_day=False):
    """(date یا datetime میلادی) از متن شمسی؛ سال میلادی (۲۰۲۶/...) هم پذیرفته می‌شود. خطا ← ValueError."""
    match = _PATTERN.match(en_digits(text or "").replace("٫", "/"))
    if not match:
        raise ValueError("تاریخ را به شکل ۱۴۰۵/۰۷/۲۰ (و در صورت نیاز ساعت ۱۴:۳۰) بنویسید.")
    year, month, day = (int(match.group(i)) for i in (1, 2, 3))
    hour = int(match.group(4)) if match.group(4) else (23 if end_of_day else 0)
    minute = int(match.group(5)) if match.group(5) else (59 if end_of_day and not match.group(4) else 0)
    try:
        if year > 1700:  # میلادی
            date = datetime.date(year, month, day)
        else:
            date = jdatetime.date(year, month, day).togregorian()
        moment = datetime.datetime.combine(date, datetime.time(hour, minute))
    except ValueError as exc:
        raise ValueError("این تاریخ وجود ندارد.") from exc
    return date, moment, bool(match.group(4))


class JalaliDateTimeInput(forms.TextInput):
    def __init__(self, attrs=None, with_time=True):
        self.with_time = with_time
        defaults = {"dir": "ltr", "data-jalali": "datetime" if with_time else "date", "autocomplete": "off",
                    "placeholder": "۱۴۰۵/۰۷/۲۰ ۱۴:۳۰" if with_time else "۱۴۰۵/۰۷/۲۰"}
        super().__init__({**defaults, **(attrs or {})})

    def format_value(self, value):
        if isinstance(value, (datetime.date, datetime.datetime)):
            return to_jalali_text(value, self.with_time)
        return value or ""


class JalaliDateTimeField(forms.Field):
    widget = JalaliDateTimeInput
    default_error_messages = {"invalid": "تاریخ نامعتبر است."}

    def __init__(self, *, end_of_day=False, **kwargs):
        self.end_of_day = end_of_day  # «تا ۱۴۰۵/۰۸/۰۱» بدون ساعت یعنی تا پایان آن روز
        kwargs.setdefault("help_text", "شمسی؛ مثلاً ۱۴۰۵/۰۷/۲۰ ۱۴:۳۰")
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime.datetime):
            return value
        try:
            _date, moment, _ = parse_jalali(value, end_of_day=self.end_of_day)
        except ValueError as exc:
            raise forms.ValidationError(str(exc), code="invalid") from exc
        return timezone.make_aware(moment) if timezone.is_naive(moment) else moment


class JalaliDateField(forms.Field):
    default_error_messages = {"invalid": "تاریخ نامعتبر است."}

    def __init__(self, **kwargs):
        kwargs.setdefault("widget", JalaliDateTimeInput(with_time=False))
        kwargs.setdefault("help_text", "شمسی؛ مثلاً ۱۴۰۵/۰۷/۲۰")
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime.date):
            return value
        try:
            date, _moment, _ = parse_jalali(value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc), code="invalid") from exc
        return date


class JalaliAdminMixin:
    """ModelAdmin / Inline: فیلدهای DateTimeField و DateField قابل ویرایش ← تاریخ شمسی با تقویم."""

    class Media:
        js = ("js/jalali-picker.js",)
        css = {"all": ("css/jalali-picker.css",)}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.DateTimeField) and db_field.editable and not db_field.auto_now \
                and not db_field.auto_now_add:
            return JalaliDateTimeField(label=db_field.verbose_name, required=not db_field.blank,
                                       help_text=db_field.help_text or "شمسی؛ مثلاً ۱۴۰۵/۰۷/۲۰ ۱۴:۳۰")
        if isinstance(db_field, models.DateField) and not isinstance(db_field, models.DateTimeField) \
                and db_field.editable and not db_field.auto_now and not db_field.auto_now_add:
            return JalaliDateField(label=db_field.verbose_name, required=not db_field.blank)
        return super().formfield_for_dbfield(db_field, request, **kwargs)
