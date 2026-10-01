"""تگ‌های قالب نظرات؛ صفحه محصول بدون وابستگی کاتالوگ به اپ نظرات، نظرها را نمایش می‌دهد."""

from django import template

from ..forms import ReviewForm
from ..selectors import approved_reviews

register = template.Library()


@register.simple_tag
def product_reviews(product):
    return approved_reviews(product)


@register.simple_tag(takes_context=True)
def review_form_for(context, product):
    form = context.get("review_form")
    if isinstance(form, ReviewForm):
        return form
    user = context["request"].user
    return ReviewForm(initial={"name": user.display_name} if user.is_authenticated else {})
