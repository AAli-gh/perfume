"""سرویس‌های نظرات و پرسش و پاسخ."""

from django.conf import settings
from django.utils.module_loading import import_string

from .models import Question, Review, ReviewPhoto


def is_verified_buyer(user, product):
    """نشان «خریدار تأییدشده»؛ بررسی خرید با تابع REVIEWS_PURCHASE_CHECK (وارونگی وابستگی به سفارش‌ها)."""
    path = getattr(settings, "REVIEWS_PURCHASE_CHECK", "")
    return bool(path) and bool(import_string(path)(user, product))


def submit_review(product, form, user=None, photos=()) -> Review:
    """ثبت نظر کاربر؛ نظرها همیشه در انتظار تأیید مدیر ذخیره می‌شوند."""
    review = form.save(commit=False)
    review.product = product
    review.user = user if user is not None and user.is_authenticated else None
    review.is_approved = False
    review.is_verified = is_verified_buyer(review.user, product)
    review.save()
    for photo in photos:
        ReviewPhoto.objects.create(review=review, image=photo)
    return review


def submit_question(product, form, user=None) -> Question:
    question = form.save(commit=False)
    question.product = product
    question.user = user if user is not None and user.is_authenticated else None
    question.is_approved = False
    question.save()
    return question
