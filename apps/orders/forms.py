from django import forms

from apps.accounts.models import Address
from apps.accounts.services import default_address
from apps.core.forms import StyledFormMixin, en_digits
from apps.core.geo import PROVINCES
from apps.core.stores import get_current_store

from apps.catalog.selectors import gift_box_variants
from apps.shipping.selectors import active_methods

from .integration import online_payment_available

from . import packaging as gift
from .models import Order


class ShippingMethodField(forms.TypedChoiceField):
    """انتخاب روش ارسال از میان روش‌های فعال همان فروشگاه (بدون کوئری اضافه برای اعتبارسنجی)."""

    def __init__(self, methods):
        self.methods = {str(m.pk): m for m in methods}
        super().__init__(label="روش ارسال", choices=[(k, f"{m.name} · {m.description}" if m.description else m.name)
                                  for k, m in self.methods.items()],
                         coerce=self.methods.get, initial=next(iter(self.methods)), widget=forms.RadioSelect,
                         error_messages={"required": "روش ارسال را انتخاب کنید."})


class GiftBoxField(forms.TypedChoiceField):
    """انتخاب یک باکس هدیه موجود در صفحه تسویه (وقتی باکسی در سبد نیست)."""

    def __init__(self, variants):
        self.variants = {str(v.pk): v for v in variants}
        super().__init__(label="باکس هدیه", choices=[("", "بدون باکس")] + [(k, v.product.name) for k, v in self.variants.items()],
                         coerce=self.variants.get, required=False, empty_value=None, widget=forms.RadioSelect)


class CheckoutForm(StyledFormMixin, forms.ModelForm):
    province = forms.ChoiceField(label="استان", choices=[("", "انتخاب کنید")] + [(p, p) for p in PROVINCES])
    accept_terms = forms.BooleanField(
        label="قوانین و مقررات سایت را خوانده‌ام و می‌پذیرم.",
        error_messages={"required": "برای ثبت سفارش باید قوانین را بپذیرید."},
    )

    class Meta:
        model = Order
        fields = [
            "first_name", "last_name", "phone", "email", "province", "city",
            "address", "postal_code", "note", "payment_method",
            "packaging", "packaging_note", "gift_message", "gift_from", "hide_prices",
        ]
        widgets = {
            "phone": forms.TextInput(attrs={"placeholder": "09xxxxxxxxx", "dir": "ltr", "inputmode": "numeric"}),
            "email": forms.EmailInput(attrs={"dir": "ltr"}),
            "postal_code": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}),
            "address": forms.TextInput(attrs={"placeholder": "خیابان، کوچه، پلاک، واحد"}),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "مثلاً: ساعت مناسب تحویل"}),
            "payment_method": forms.RadioSelect,
            "packaging": forms.RadioSelect,
            "packaging_note": forms.Textarea(attrs={"rows": 3, "maxlength": 500,
                                                    "placeholder": "مثلاً: دو عطر داخل باکس و یکی جدا؛ روبان قرمز"}),
            "gift_message": forms.Textarea(attrs={"rows": 3, "maxlength": 300, "placeholder": "تولدت مبارک! …"}),
            "gift_from": forms.TextInput(attrs={"placeholder": "نام شما روی کارت"}),
        }

    def __init__(self, *args, store=None, cart=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cart_lines = list(cart) if cart is not None else []
        self.cart_contents = gift.contents(self.cart_lines)
        choices = list(Order.PaymentMethod.choices)
        if not online_payment_available(store or get_current_store()):
            choices = [c for c in choices if c[0] != Order.PaymentMethod.ONLINE]
        self.fields["payment_method"].choices = choices
        self.fields["payment_method"].initial = choices[0][0]

        self.shipping_methods = active_methods(store or get_current_store())
        if self.shipping_methods:
            self.fields["shipping_method"] = ShippingMethodField(self.shipping_methods)

        # باکس هدیه: اگر در سبد باکسی نیست، از همین‌جا انتخاب می‌شود
        self.gift_boxes = [] if self.cart_contents.boxes else list(gift_box_variants(store or get_current_store()))
        if self.gift_boxes:
            self.fields["gift_box"] = GiftBoxField(self.gift_boxes)
        self.fields["packaging"].required = False  # بدون انتخاب: بسته‌بندی معمولی
        self.fields["packaging"].initial = (Order.Packaging.IN_BOX if self.cart_contents.boxes and self.cart_contents.perfumes
                                            else Order.Packaging.SEPARATE if self.cart_contents.boxes
                                            else Order.Packaging.NONE)

    def gift_box_options(self):
        """(radio, variant) برای نمایش کارت باکس‌ها؛ گزینه «بدون باکس» variant ندارد (None)."""
        if "gift_box" not in self.fields:
            return []
        variants = self.fields["gift_box"].variants
        return [(radio, variants.get(str(radio.data["value"]))) for radio in self["gift_box"]]

    def chosen_gift_box(self):
        """باکس انتخاب‌شده در داده‌های خام فرم (برای پیش‌نمایش قیمت، حتی وقتی بقیه فرم ناقص است)."""
        if not self.gift_boxes or self.data.get("packaging", Order.Packaging.NONE) == Order.Packaging.NONE:
            return None
        return self.fields["gift_box"].variants.get(self.data.get("gift_box", ""))

    def clean(self):
        data = super().clean()
        method, province = data.get("shipping_method"), data.get("province")
        if method is not None and province and not method.serves(province):
            self.add_error("shipping_method", f"«{method.name}» به استان {province} ارسال نمی‌کند.")
        packaging = data.get("packaging") or Order.Packaging.NONE
        if packaging == Order.Packaging.NONE:
            data["gift_box"] = None  # باکسی که بدون انتخاب بسته‌بندی هدیه علامت خورده، اضافه نمی‌شود
        for field, message in gift.validate(packaging, data.get("packaging_note"), self.cart_lines,
                                            data.get("gift_box")).items():
            self.add_error(field if field in self.fields else None, message)
        return data

    def clean_packaging(self):
        return self.cleaned_data.get("packaging") or Order.Packaging.NONE

    def clean_phone(self):
        return en_digits(self.cleaned_data["phone"])

    def clean_postal_code(self):
        return en_digits(self.cleaned_data["postal_code"])


def checkout_initial(user):
    """مقادیر اولیه فرم تسویه از روی آدرس پیش‌فرض یا پروفایل کاربر واردشده."""
    if not user.is_authenticated:
        return {}
    initial = {"first_name": user.first_name, "last_name": user.last_name, "email": user.email, "phone": user.phone}
    address = default_address(user)
    if address is not None:
        initial.update({f: getattr(address, f) for f in Address.FIELDS})
    return initial
