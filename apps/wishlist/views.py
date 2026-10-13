from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .services import price_alerts, set_price_alert, toggle, wishlist_products
from apps.core.ratelimit import ratelimit


@ratelimit("wishlist", "60/1m")
@require_POST
def toggle_view(request, product_id):
    product = get_object_or_404(Product.objects.for_store(request.store).active(), pk=product_id)
    if not request.user.is_authenticated:
        if request.htmx:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = f"{reverse('accounts:login')}?next={product.get_absolute_url()}"
            return resp
        return redirect_to_login(product.get_absolute_url())
    active = toggle(request.user, product)
    if request.htmx:
        return render(request, "wishlist/partials/button.html", {"product": product, "active": active})
    return redirect(product.get_absolute_url())


@login_required
def list_view(request):
    return render(request, "wishlist/list.html", {
        "products": wishlist_products(request.user, request.store), "alerts": price_alerts(request.user),
    })


@login_required
@require_POST
def price_alert_view(request, product_id):
    """روشن/خاموش کردن «خبرم کن وقتی قیمت پایین آمد» برای یک محصول علاقه‌مندی."""
    product = get_object_or_404(Product.objects.for_store(request.store), pk=product_id)
    enabled = request.POST.get("enabled") == "1"
    set_price_alert(request.user, product, enabled)
    if request.htmx:
        return render(request, "wishlist/partials/price_alert.html", {"p": product, "on": enabled})
    return redirect("wishlist:list")
