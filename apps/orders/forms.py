from django import forms

from apps.accounts.models import Address
from apps.accounts.services import default_address
from apps.core.forms import StyledFormMixin, en_digits
from apps.core.geo import PROVINCES
from apps.core.stores import get_current_store

from apps.shipping.selectors import active_methods

from .integration import online_payment_available

from .models import Order



class ShippingMethodField(forms.TypedChoiceField):
    """انتخاب روش ارسال از میان روش‌های فعال همان فروشگاه (بدون کوئری اضافه برای اعتبارسنجی)."""

    def __init__(self, methods):
        self.methods = {str(m.pk): m for m in methods}
        super().__init__(label="روش ارسال", choices=[(k, f"{m.name} · {m.description}" if m.description else m.name)
                                  for k, m in self.methods.items()],
                         coerce=self.methods.get, initial=next(iter(self.methods)), widget=forms.RadioSelect,
                         error_messages={"required": "روش ارسال را انتخاب کنید."})


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
        ]
        widgets = {
            "phone": forms.TextInput(attrs={"placeholder": "09xxxxxxxxx", "dir": "ltr", "inputmode": "numeric"}),
            "email": forms.EmailInput(attrs={"dir": "ltr"}),
            "postal_code": forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}),
            "address": forms.TextInput(attrs={"placeholder": "خیابان، کوچه، پلاک، واحد"}),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "مثلاً: بسته‌بندی کادویی"}),
            "payment_method": forms.RadioSelect,
        }

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = list(Order.PaymentMethod.choices)
        if not online_payment_available(store or get_current_store()):
            choices = [c for c in choices if c[0] != Order.PaymentMethod.ONLINE]
        self.fields["payment_method"].choices = choices
        self.fields["payment_method"].initial = choices[0][0]

        self.shipping_methods = active_methods(store or get_current_store())
        if self.shipping_methods:
            self.fields["shipping_method"] = ShippingMethodField(self.shipping_methods)

    def clean(self):
        data = super().clean()
        method, province = data.get("shipping_method"), data.get("province")
        if method is not None and province and not method.serves(province):
            self.add_error("shipping_method", f"«{method.name}» به استان {province} ارسال نمی‌کند.")
        return data

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
