from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import NewsletterForm


@require_POST
def newsletter(request):
    form = NewsletterForm(request.POST)
    ok = form.is_valid()
    if ok:
        form.save(request.store)
        form = NewsletterForm()
    if request.htmx:
        return render(request, "marketing/partials/newsletter.html", {"newsletter_form": form, "ok": ok})
    if ok:
        messages.success(request, "عضویت شما در خبرنامه انجام شد.")
    return redirect("pages:home")
