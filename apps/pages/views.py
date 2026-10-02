from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import ContactForm
from .services import build_blocks, ensure_home_page, rendered_status


def home(request):
    page = ensure_home_page(request.store)
    blocks = build_blocks(page, request, status=rendered_status(page, request))
    return render(request, "pages/home.html", {"page": page, "blocks": blocks})


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
