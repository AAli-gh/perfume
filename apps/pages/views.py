from django.contrib import messages
from django.shortcuts import redirect, render

from apps.blog.models import Post
from apps.catalog import selectors as catalog
from apps.catalog.models import Collection
from apps.marketing.forms import NewsletterForm

from .forms import ContactForm


def home(request):
    return render(request, "pages/home.html", {
        "collections": Collection.objects.for_store(request.store)[:3],
        "bestsellers": catalog.best_sellers(request.store, limit=8),
        "posts": Post.objects.for_store(request.store).published().select_related("category")[:2],
        "newsletter_form": NewsletterForm(),
    })


def about(request):
    return render(request, "pages/about.html")


def contact(request):
    form = ContactForm(request.POST or None)
    sent = False
    if request.method == "POST" and form.is_valid():
        msg = form.save(commit=False)
        msg.store = request.store
        msg.save()
        sent = True
        form = ContactForm()
        if not request.htmx:
            messages.success(request, f"{msg.name} عزیز، پیام شما دریافت شد.")
            return redirect("pages:contact")
    template = "pages/partials/contact_form.html" if request.htmx else "pages/contact.html"
    return render(request, template, {"form": form, "sent": sent})
