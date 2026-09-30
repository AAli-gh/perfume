from django import forms
from django.conf import settings

from core.forms import StyledFormMixin, en_digits

from .models import Order

PROVINCES = [
    "آذربایجان شرقی", "آذربایجان غربی", "اردبیل", "اصفهان", "البرز", "ایلام", "بوشهر", "تهران",
    "چهارمحال و بختیاری", "خراسان جنوبی", "خراسان رضوی", "خراسان شمالی", "خوزستان", "زنجان", "سمنان",
    "سیستان و بلوچستان", "فارس", "قزوین", "قم", "کردستان", "کرمان", "کرمانشاه", "کهگیلویه و بویراحمد",
    "گلستان", "گیلان", "لرستان", "مازندران", "مرکزی", "هرمزگان", "همدان", "یزد",
]


def online_payment_available():
    """درگاه آزمایشی فقط در حالت DEBUG مجاز است."""
    return bool(settings.ZARINPAL_MERCHANT_ID) or settings.DEBUG


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = list(Order.PaymentMethod.choices)
        if not online_payment_available():
            choices = [c for c in choices if c[0] != Order.PaymentMethod.ONLINE]
        self.fields["payment_method"].choices = choices
        self.fields["payment_method"].initial = choices[0][0]

    def clean_phone(self):
        return en_digits(self.cleaned_data["phone"])

    def clean_postal_code(self):
        return en_digits(self.cleaned_data["postal_code"])
