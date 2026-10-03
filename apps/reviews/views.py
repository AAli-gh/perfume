from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .forms import ReviewForm
from .services import submit_review
from apps.core.ratelimit import ratelimit


@ratelimit("review", "5/10m")
@require_POST
def create(request, slug):
    product = get_object_or_404(Product.objects.for_store(request.store).active(), slug=slug)
    form = ReviewForm(request.POST)
    submitted = form.is_valid()
    if submitted:
        submit_review(product, form, request.user)
        form = ReviewForm()
    context = {"product": product, "review_form": form, "submitted": submitted}
    if request.htmx:
        return render(request, "reviews/partials/review_form.html", context)
    if submitted:
        messages.success(request, "نظر شما ثبت شد و پس از تأیید نمایش داده می‌شود.")
    return redirect(product.get_absolute_url() + "#reviews")
