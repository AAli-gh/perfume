from django import forms

from apps.core.forms import StyledFormMixin, en_digits
from apps.core.validators import iran_mobile_validator



class ShopFilterForm(forms.Form):
    SORTS = [
        ("", "پیش‌فرض"),
        ("rating", "محبوب‌ترین"),
        ("price", "ارزان‌ترین"),
        ("-price", "گران‌ترین"),
        ("new", "جدیدترین"),
    ]
    q = forms.CharField(required=False)
    brand = forms.MultipleChoiceField(required=False)
    scent = forms.MultipleChoiceField(required=False)
    collection = forms.CharField(required=False)
    category = forms.CharField(required=False)
    min_price = forms.IntegerField(required=False, min_value=0)
    max_price = forms.IntegerField(required=False, min_value=0)
    sort = forms.ChoiceField(required=False, choices=SORTS)

    def __init__(self, *args, brands=(), scents=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].choices = [(b.slug, b.name) for b in brands]
        self.fields["scent"].choices = [(s.slug, s.name) for s in scents]


class PhoneField(forms.CharField):
    """موبایل با ارقام فارسی یا لاتین (پیش از اعتبارسنجی به لاتین تبدیل می‌شود)."""

    def to_python(self, value):
        return en_digits(super().to_python(value)).replace(" ", "")


class BackInStockForm(StyledFormMixin, forms.Form):
    """«موجود شد خبرم کن» برای حجم‌های ناموجود یک محصول."""

    variant = forms.TypedChoiceField(label="حجم", coerce=int)
    phone = PhoneField(label="موبایل", max_length=11, validators=[iran_mobile_validator],
                            widget=forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric",
                                                          "placeholder": "09xxxxxxxxx"}))

    def __init__(self, *args, variants=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.variants = {v.pk: v for v in variants}
        self.fields["variant"].choices = [(v.pk, f"{v.price:,} تومان" if v.product.is_accessory else f"{v.size_ml} میل")
                                          for v in variants]
        if len(self.variants) == 1:
            self.fields["variant"].widget = forms.HiddenInput()
            self.fields["variant"].initial = next(iter(self.variants))

    def clean_variant(self):
        return self.variants[self.cleaned_data["variant"]]
