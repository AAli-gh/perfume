from django import forms

from apps.core.forms import StyledFormMixin

from .models import Review


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
    min_price = forms.IntegerField(required=False, min_value=0)
    max_price = forms.IntegerField(required=False, min_value=0)
    sort = forms.ChoiceField(required=False, choices=SORTS)

    def __init__(self, *args, brands=(), scents=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].choices = [(b.slug, b.name) for b in brands]
        self.fields["scent"].choices = [(s.slug, s.name) for s in scents]


class ReviewForm(StyledFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="امتیاز", coerce=int, initial=5,
        choices=[(5, "★★★★★ عالی"), (4, "★★★★ خوب"), (3, "★★★ متوسط"), (2, "★★ ضعیف"), (1, "★ بد")],
    )

    class Meta:
        model = Review
        fields = ["name", "rating", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 5:
            raise forms.ValidationError("متن نظر خیلی کوتاه است.")
        return text
