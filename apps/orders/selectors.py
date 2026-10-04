from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Order

SESSION_ORDERS = "orders"


def remember_order(request, order):
    """شماره سفارش در session مهمان نگه داشته می‌شود تا بتواند سفارشش را ببیند/پرداخت کند."""
    numbers = request.session.get(SESSION_ORDERS, [])
    request.session[SESSION_ORDERS] = (numbers + [order.number])[-20:]


def get_owned_order(request, number):
    """سفارش فروشگاه جاری که متعلق به همین کاربر/نشست باشد (یا کارمند)؛ در غیر این صورت 404."""
    order = get_object_or_404(Order.objects.for_store(request.store).prefetch_related("items"), number=number)
    owns = (
        number in request.session.get(SESSION_ORDERS, [])
        or (request.user.is_authenticated and order.user_id == request.user.pk)
        or request.user.is_staff
    )
    if not owns:
        raise Http404
    return order
