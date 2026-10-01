from django import forms

from apps.core.forms import StyledFormMixin

from .models import Review


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
