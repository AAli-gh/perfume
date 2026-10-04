"""سرویس‌های حساب کاربری."""

from django.db import transaction

from .models import Address


@transaction.atomic
def remember_address(user, data):
    """آدرس استفاده‌شده در سفارش را به‌عنوان آدرس پیش‌فرض کاربر ذخیره می‌کند (بدون ایجاد تکرار)."""
    if not user or not user.is_authenticated:
        return None
    values = {f: data[f] for f in Address.FIELDS}
    address = Address.objects.filter(user=user, **values).first()
    Address.objects.filter(user=user, is_default=True).exclude(pk=getattr(address, "pk", None)).update(is_default=False)
    if address is None:
        address = Address.objects.create(user=user, is_default=True, **values)
    elif not address.is_default:
        address.is_default = True
        address.save(update_fields=["is_default"])
    return address


def default_address(user):
    if not user or not user.is_authenticated:
        return None
    return user.addresses.filter(is_default=True).first() or user.addresses.first()
