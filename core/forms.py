from django import forms

from .models import ContactMessage, NewsletterSubscriber

FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def en_digits(value):
    return (value or "").translate(FA_TO_EN).strip()


class StyledFormMixin:
    """افزودن کلاس input به همه ویجت‌ها (Tailwind)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                continue
            widget.attrs.setdefault("class", "input")


class ContactForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "نام شما"}),
            "email": forms.EmailInput(attrs={"placeholder": "ایمیل شما", "dir": "ltr"}),
            "message": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_message(self):
        msg = self.cleaned_data["message"].strip()
        if len(msg) < 10:
            raise forms.ValidationError("پیام باید حداقل ۱۰ کاراکتر باشد.")
        return msg


class NewsletterForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label="ایمیل", widget=forms.EmailInput(attrs={"placeholder": "آدرس ایمیل شما", "dir": "ltr"}))

    def save(self):
        NewsletterSubscriber.objects.get_or_create(email=self.cleaned_data["email"].lower())
