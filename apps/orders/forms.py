from django import forms

from apps.accounts.models import Address
from apps.accounts.services import default_address
from apps.core.forms import StyledFormMixin, en_digits
from apps.core.stores import get_current_store

from .integration import online_payment_available

from .models import Order

PROVINCES = [
    "آذربایجان شرقی", "آذربایجان غربی", "اردبیل", "اصفهان", "البرز", "ایلام", "بوشهر", "تهران",
    "چهارمحال و بختیاری", "خراسان جنوبی", "خراسان رضوی", "خراسان شمالی", "خوزستان", "زنجان", "سمنان",
    "سیستان و بلوچستان", "فارس", "قزوین", "قم", "کردستان", "کرمان", "کرمانشاه", "کهگیلویه و بویراحمد",
    "گلستان", "گیلان", "لرستان", "مازندران", "مرکزی", "هرمزگان", "همدان", "یزد",
]


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
