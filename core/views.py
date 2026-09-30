from django.contrib import messages
from django.db.models import F
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from blog.models import Post
from catalog.models import Collection
from catalog.views import product_queryset

from .forms import ContactForm, NewsletterForm


def home(request):
    return render(request, "core/home.html", {
        "collections": Collection.objects.all()[:3],
        "bestsellers": product_queryset().order_by(F("rating_avg").desc(nulls_last=True), "-review_count")[:8],
        "posts": Post.objects.published().select_related("category")[:2],
        "newsletter_form": NewsletterForm(),
    })


def about(request):
    return render(request, "core/about.html")


def contact(request):
    form = ContactForm(request.POST or None)
    sent = False
    if request.method == "POST" and form.is_valid():
        msg = form.save()
        sent = True
        form = ContactForm()
        if not request.htmx:
            messages.success(request, f"{msg.name} عزیز، پیام شما دریافت شد.")
            return redirect("core:contact")
    template = "core/partials/contact_form.html" if request.htmx else "core/contact.html"
    return render(request, template, {"form": form, "sent": sent})


@require_POST
def newsletter(request):
    form = NewsletterForm(request.POST)
    ok = form.is_valid()
    if ok:
        form.save()
        form = NewsletterForm()
    if request.htmx:
        return render(request, "core/partials/newsletter.html", {"newsletter_form": form, "ok": ok})
    if ok:
        messages.success(request, "عضویت شما در خبرنامه انجام شد.")
    return redirect("core:home")
