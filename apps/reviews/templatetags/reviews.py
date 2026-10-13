"""تگ‌های قالب نظرات؛ صفحه محصول بدون وابستگی کاتالوگ به اپ نظرات، نظرها را نمایش می‌دهد."""

from django import template

from ..forms import QuestionForm, ReviewForm
from ..selectors import answered_questions, approved_reviews

register = template.Library()


def _initial(context):
    user = context["request"].user
    return {"name": user.display_name} if user.is_authenticated else {}


@register.simple_tag
def product_reviews(product):
    return approved_reviews(product)


@register.simple_tag(takes_context=True)
def review_form_for(context, product):
    form = context.get("review_form")
    if isinstance(form, ReviewForm):
        return form
    return ReviewForm(initial=_initial(context))


@register.simple_tag
def product_questions(product):
    return answered_questions(product)


@register.simple_tag(takes_context=True)
def question_form_for(context, product):
    form = context.get("question_form")
    if isinstance(form, QuestionForm):
        return form
    return QuestionForm(initial=_initial(context))
