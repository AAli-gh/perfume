"""سرویس‌های نظرات."""

from .models import Review


def submit_review(product, form, user=None) -> Review:
    """ثبت نظر کاربر؛ نظرها همیشه در انتظار تأیید مدیر ذخیره می‌شوند."""
    review = form.save(commit=False)
    review.product = product
    review.user = user if user is not None and user.is_authenticated else None
    review.is_approved = False
    review.save()
    return review
