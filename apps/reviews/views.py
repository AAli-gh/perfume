from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .forms import QuestionForm, ReviewForm
from .services import submit_question, submit_review
from apps.core.ratelimit import ratelimit


@ratelimit("review", "5/10m")
@require_POST
def create(request, slug):
    product = get_object_or_404(Product.objects.for_store(request.store).active(), slug=slug)
    form = ReviewForm(request.POST, request.FILES)
    submitted = form.is_valid()
    if submitted:
        submit_review(product, form, request.user, form.cleaned_data["photos"])
        form = ReviewForm()
    context = {"product": product, "review_form": form, "submitted": submitted}
    if request.htmx:
        return render(request, "reviews/partials/review_form.html", context)
    if submitted:
        messages.success(request, "نظر شما ثبت شد و پس از تأیید نمایش داده می‌شود.")
    return redirect(product.get_absolute_url() + "#reviews")


@ratelimit("question", "5/10m")
@require_POST
def ask(request, slug):
    """پرسش زیر محصول؛ پس از پاسخ و تأیید فروشگاه نمایش داده می‌شود."""
    product = get_object_or_404(Product.objects.for_store(request.store).active(), slug=slug)
    form = QuestionForm(request.POST)
    submitted = form.is_valid()
    if submitted:
        submit_question(product, form, request.user)
        form = QuestionForm()
    context = {"product": product, "question_form": form, "asked": submitted}
    if request.htmx:
        return render(request, "reviews/partials/question_form.html", context)
    if submitted:
        messages.success(request, "پرسش شما ثبت شد و پس از پاسخ فروشگاه نمایش داده می‌شود.")
    return redirect(product.get_absolute_url() + "#questions")
