"""اعتبارسنج‌های مشترک (ایران)."""

from django.core.validators import RegexValidator

iran_mobile_validator = RegexValidator(r"^09\d{9}$", "شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.")
postal_code_validator = RegexValidator(r"^\d{10}$", "کد پستی باید ۱۰ رقم باشد.")


# ---------- آپلود تصویر (لوگو، فاوآیکون، تصاویر بخش‌ها) ----------
# SVG عمداً مجاز نیست: فایل SVG می‌تواند اسکریپت داشته باشد و از دامنه خود سایت سرو می‌شود.
UPLOAD_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")


def validate_image_upload(file, *, max_mb=3, extensions=UPLOAD_IMAGE_EXTENSIONS):
    from django.core.exceptions import ValidationError

    if not file:
        return
    name = (getattr(file, "name", "") or "").lower()
    if "." not in name or name.rsplit(".", 1)[1] not in extensions:
        raise ValidationError(f"فقط این قالب‌ها مجازند: {', '.join(extensions)}")
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"حجم فایل حداکثر {max_mb} مگابایت")
