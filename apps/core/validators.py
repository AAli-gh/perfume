"""اعتبارسنج‌های مشترک (ایران)."""

from django.core.validators import RegexValidator

iran_mobile_validator = RegexValidator(r"^09\d{9}$", "شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.")
postal_code_validator = RegexValidator(r"^\d{10}$", "کد پستی باید ۱۰ رقم باشد.")
