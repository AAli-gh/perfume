"""تاریخ شمسی در فرم‌ها و پنل مدیریت."""

import datetime

import pytest
from django import forms
from django.contrib import admin
from django.utils import timezone

from apps.core import jalali as J


def test_to_jalali_text():
    assert J.to_jalali_text(None) == ""
    assert J.to_jalali_text(datetime.date(2026, 10, 12)) == "۱۴۰۵/۰۷/۲۰"
    moment = timezone.make_aware(datetime.datetime(2026, 10, 12, 14, 30))
    assert J.to_jalali_text(moment) == "۱۴۰۵/۰۷/۲۰ ۱۴:۳۰"
    assert J.to_jalali_text(datetime.datetime(2026, 10, 12, 9, 5), with_time=False) == "۱۴۰۵/۰۷/۲۰"


@pytest.mark.parametrize("text,expected", [
    ("۱۴۰۵/۰۷/۲۰", (datetime.date(2026, 10, 12), datetime.datetime(2026, 10, 12, 0, 0), False)),
    ("1405-7-20 14:30", (datetime.date(2026, 10, 12), datetime.datetime(2026, 10, 12, 14, 30), True)),
    ("2026/10/12", (datetime.date(2026, 10, 12), datetime.datetime(2026, 10, 12, 0, 0), False)),  # میلادی
])
def test_parse_jalali(text, expected):
    assert J.parse_jalali(text) == expected


def test_parse_jalali_end_of_day_and_errors():
    assert J.parse_jalali("1405/07/20", end_of_day=True)[1] == datetime.datetime(2026, 10, 12, 23, 59)
    with pytest.raises(ValueError, match="۱۴۰۵/۰۷/۲۰"):
        J.parse_jalali("فردا")
    with pytest.raises(ValueError, match="وجود ندارد"):
        J.parse_jalali("1405/13/40")


def test_widget_and_fields():
    widget = J.JalaliDateTimeInput()
    assert widget.format_value(datetime.date(2026, 10, 12)) == "۱۴۰۵/۰۷/۲۰" and widget.format_value(None) == ""
    assert widget.attrs["data-jalali"] == "datetime"
    field = J.JalaliDateTimeField(required=False, end_of_day=True)
    assert field.clean("") is None
    moment = timezone.now()
    assert field.to_python(moment) is moment
    assert timezone.localtime(field.clean("1405/07/20")).hour == 23
    with pytest.raises(forms.ValidationError):
        field.clean("x")
    date_field = J.JalaliDateField(required=False)
    assert date_field.clean("") is None and date_field.clean("1405/07/20") == datetime.date(2026, 10, 12)
    assert date_field.to_python(datetime.date(2026, 1, 1)) == datetime.date(2026, 1, 1)
    with pytest.raises(forms.ValidationError):
        date_field.clean("1405/02/31x")


def test_admin_mixin_uses_jalali_fields():
    from apps.discounts.models import Coupon

    class CouponAdmin(J.JalaliAdminMixin, admin.ModelAdmin):
        pass

    model_admin = CouponAdmin(Coupon, admin.site)
    date_fields = [f for f in Coupon._meta.fields if f.get_internal_type() == "DateTimeField" and f.editable
                   and not f.auto_now and not f.auto_now_add]
    assert date_fields, "Coupon باید فیلد تاریخ قابل ویرایش داشته باشد"
    assert isinstance(model_admin.formfield_for_dbfield(date_fields[0], request=None), J.JalaliDateTimeField)
    code_field = Coupon._meta.get_field("code")
    assert not isinstance(model_admin.formfield_for_dbfield(code_field, request=None), J.JalaliDateTimeField)
