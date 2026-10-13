from django import forms

from apps.core.forms import StyledFormMixin
from apps.core.validators import validate_image_upload

from .models import Question, Review

MAX_PHOTOS = 3


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplePhotoField(forms.FileField):
    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = [f for f in (data if isinstance(data, (list, tuple)) else [data]) if f]
        if len(files) > MAX_PHOTOS:
            raise forms.ValidationError(f"حداکثر {MAX_PHOTOS} عکس می‌توانید بفرستید.")
        for f in files:
            super().clean(f, initial)
            validate_image_upload(f)
        return files


class ReviewForm(StyledFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="امتیاز", coerce=int, initial=5,
        choices=[(5, "★★★★★ عالی"), (4, "★★★★ خوب"), (3, "★★★ متوسط"), (2, "★★ ضعیف"), (1, "★ بد")],
    )
    photos = MultiplePhotoField(label="عکس (اختیاری)", help_text=f"تا {MAX_PHOTOS} عکس JPG یا PNG، هر کدام حداکثر ۳ مگابایت",
                                widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))

    class Meta:
        model = Review
        fields = ["name", "rating", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 5:
            raise forms.ValidationError("متن نظر خیلی کوتاه است.")
        return text


class QuestionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Question
        fields = ["name", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "مثلاً: ماندگاری این عطر روی لباس چقدر است؟"})}

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 8:
            raise forms.ValidationError("پرسش خیلی کوتاه است.")
        return text
