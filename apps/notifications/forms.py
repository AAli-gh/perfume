from django import forms

from apps.core.forms import StyledFormMixin, en_digits
from apps.core.validators import iran_mobile_validator


class PhoneForm(StyledFormMixin, forms.Form):
    phone = forms.CharField(
        label="شماره موبایل", max_length=11,
        widget=forms.TextInput(attrs={"placeholder": "09xxxxxxxxx", "dir": "ltr", "inputmode": "numeric",
                                      "autocomplete": "tel", "autofocus": True}),
    )

    def clean_phone(self):
        phone = en_digits(self.cleaned_data["phone"])
        iran_mobile_validator(phone)
        return phone


class CodeForm(PhoneForm):
    code = forms.CharField(
        label="کد پیامک‌شده", max_length=6, min_length=6,
        widget=forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric", "autocomplete": "one-time-code",
                                      "autofocus": True}),
    )

    def clean_code(self):
        return en_digits(self.cleaned_data["code"])
