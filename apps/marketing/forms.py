from django import forms

from apps.core.forms import StyledFormMixin

from .models import NewsletterSubscriber


class NewsletterForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label="ایمیل", widget=forms.EmailInput(attrs={"placeholder": "آدرس ایمیل شما", "dir": "ltr"}))

    def save(self, store):
        NewsletterSubscriber.objects.get_or_create(store=store, email=self.cleaned_data["email"].lower())
