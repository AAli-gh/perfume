"""عطرهای اخیراً دیده‌شده (نشست کاربر) — برای پیشنهاد به کاربران مهمان و جدید."""

SESSION_KEY = "recently_viewed"
LIMIT = 12


def remember_view(request, product):
    current = request.session.get(SESSION_KEY, [])
    updated = [product.pk, *(pk for pk in current if pk != product.pk)][:LIMIT]
    if updated != current:  # بازدید دوباره همان عطر، نشست را دوباره ذخیره نمی‌کند
        request.session[SESSION_KEY] = updated


def recently_viewed_ids(request):
    return [pk for pk in request.session.get(SESSION_KEY, []) if isinstance(pk, int)]
