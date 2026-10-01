"""تگ قالب فرم تسویه‌حساب؛ صفحه سبد خرید بدون import مستقیم از orders در cart، فرم را نمایش می‌دهد."""

from django import template

from ..forms import CheckoutForm, checkout_initial

register = template.Library()


@register.simple_tag(takes_context=True)
def checkout_form(context):
    """فرم موجود در context (مثلاً با خطاهای اعتبارسنجی) یا یک فرم تازه با اطلاعات کاربر."""
    form = context.get("form")
    if isinstance(form, CheckoutForm):
        return form
    request = context["request"]
    return CheckoutForm(initial=checkout_initial(request.user), store=getattr(request, "store", None))
