from django.db.models import Prefetch

from .models import Answer, Question, Review


def approved_reviews(product):
    """نظرهای تأییدشده؛ خریداران تأییدشده اول."""
    return (Review.objects.filter(product=product, is_approved=True).prefetch_related("photos")
            .order_by("-is_verified", "-created_at"))


def answered_questions(product):
    """پرسش‌های تأییدشده‌ای که دست‌کم یک پاسخ دارند."""
    return (Question.objects.filter(product=product, is_approved=True, answers__isnull=False).distinct()
            .prefetch_related(Prefetch("answers", queryset=Answer.objects.order_by("created_at"))))
