from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from core.forms import StyledFormMixin

User = get_user_model()


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(label="ایمیل", widget=forms.EmailInput(attrs={"placeholder": "آدرس ایمیل", "dir": "ltr", "autofocus": True}))
    password = forms.CharField(label="رمز عبور", strip=False, widget=forms.PasswordInput(attrs={"placeholder": "رمز عبور", "dir": "ltr"}))
    remember = forms.BooleanField(label="مرا به خاطر بسپار", required=False)

    error_messages = {
        "invalid_login": "ایمیل یا رمز عبور اشتباه است.",
        "inactive": "این حساب کاربری غیرفعال است.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].lower()


class RegisterForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "نام"}),
            "last_name": forms.TextInput(attrs={"placeholder": "نام خانوادگی"}),
            "email": forms.EmailInput(attrs={"placeholder": "آدرس ایمیل", "dir": "ltr"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["password1"].widget.attrs.update(placeholder="حداقل ۸ کاراکتر", dir="ltr")
        self.fields["password2"].widget.attrs.update(placeholder="تکرار رمز عبور", dir="ltr")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("با این ایمیل قبلاً ثبت‌نام شده است.")
        return email
