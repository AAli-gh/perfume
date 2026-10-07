"""بسته‌بندی هدیه سفارش: چیدن عطرها داخل باکس، ارسال جدای باکس یا توضیح دلخواه مشتری.

باکس هدیه یک محصول کاتالوگ (kind=gift_box) است؛ مشتری می‌تواند آن را جدا به سبد اضافه کند یا در صفحه تسویه
انتخاب کند (در این حالت یک قلم باکس به سفارش افزوده می‌شود).
"""

from dataclasses import dataclass

from .models import Order

P = Order.Packaging
NEEDS_BOX = {P.IN_BOX, P.SEPARATE}


@dataclass(frozen=True)
class Contents:
    perfumes: int  # تعداد شیشه‌های عطر
    boxes: int  # تعداد باکس‌های هدیه
    capacity: int  # گنجایش کل باکس‌ها (شیشه)


def contents(lines):
    """lines: اقلامی با variant و quantity (سبد یا سفارش)."""
    perfumes = boxes = capacity = 0
    for line in lines:
        product = line.variant.product
        if product.is_gift_box:
            boxes += line.quantity
            capacity += line.quantity * (product.gift_capacity or 0)
        else:
            perfumes += line.quantity
    return Contents(perfumes, boxes, capacity)


def validate(packaging, note, cart_lines, extra_box=None):
    """خطاها به‌صورت {field: پیام}؛ extra_box: ProductVariant باکسی که در تسویه انتخاب شده (یا None)."""
    errors = {}
    have = contents(cart_lines)
    boxes = have.boxes + (1 if extra_box else 0)
    capacity = have.capacity + ((extra_box.product.gift_capacity or 0) if extra_box else 0)
    if packaging in NEEDS_BOX and not boxes:
        errors["gift_box"] = "برای این نوع بسته‌بندی یک باکس هدیه انتخاب کنید."
    if packaging == P.IN_BOX:
        if not have.perfumes:
            errors["packaging"] = "سفارش شما عطری ندارد که داخل باکس چیده شود؛ «باکس جدا ارسال شود» را انتخاب کنید."
        elif boxes and capacity < have.perfumes:
            errors["gift_box"] = (
                f"گنجایش باکس‌ها {capacity} شیشه است ولی سفارش شما {have.perfumes} عطر دارد؛ باکس بزرگ‌تر یا "
                f"بیشتری انتخاب کنید، یا «توضیح می‌دهم» را بزنید و بنویسید چطور بسته‌بندی شود."
            )
    if packaging == P.CUSTOM and not (note or "").strip():
        errors["packaging_note"] = "توضیح دهید سفارش چطور بسته‌بندی شود."
    return errors
