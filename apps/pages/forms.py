from django import forms

from apps.core.forms import StyledFormMixin

from .models import ContactMessage


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
