from .models import ShippingMethod


def active_methods(store, province=""):
    methods = ShippingMethod.objects.for_store(store).filter(is_active=True).prefetch_related("rates")
    return [m for m in methods if m.serves(province)]


def default_method(store):
    """روش ارسال پیش‌فرض برای تخمین هزینه در سبد (قبل از انتخاب استان)."""
    methods = active_methods(store)
    return methods[0] if methods else None
