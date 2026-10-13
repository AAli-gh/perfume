"""پیام‌های پرسش و پاسخ محصول: پرسش تازه به مدیران، پاسخ فروشگاه به پرسنده."""

from django.urls import reverse

from apps.reviews.models import Answer, Question

from . import events as E
from .services import notify_event


def notify_asked(question_id):
    question = Question.objects.select_related("product__store").filter(pk=question_id).first()
    if question is None:
        return 0
    store = question.product.store
    context = {"name": question.name, "product": question.product.name, "question": question.text,
               "admin_url": store.base_url + reverse("admin:reviews_question_change", args=[question.pk])}
    return len(notify_event(store, E.QUESTION_ASKED, context, audiences=(E.STAFF,)))


def notify_answered(answer_id):
    answer = Answer.objects.select_related("question__product__store", "question__user").filter(pk=answer_id).first()
    if answer is None or not answer.is_staff or answer.question.user is None:
        return 0
    question, user = answer.question, answer.question.user
    store = question.product.store
    context = {"name": question.name, "product": question.product.name, "question": question.text,
               "answer": answer.text, "product_url": store.base_url + question.product.get_absolute_url() + "#questions"}
    return len(notify_event(store, E.QUESTION_ANSWERED, context, phone=user.phone or "", email=user.email if user.has_real_email else "",
                            audiences=(E.CUSTOMER,)))
