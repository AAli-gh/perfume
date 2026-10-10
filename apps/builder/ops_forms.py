"""فرم‌های بخش عملیات استودیو (محصولات، قیمت، مشتریان، پیامک گروهی)."""

from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.catalog.bulk import ROUNDING, PriceRule
from apps.catalog.models import Brand, Collection, ScentFamily
from apps.catalog.profile import Kind
from apps.core.forms import StyledFormMixin, en_digits
from apps.core.jalali import JalaliDateTimeField


class ImportForm(StyledFormMixin, forms.Form):
    file = forms.FileField(label="فایل Excel یا CSV",
                           widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.csv"}))


class LocalizedDecimalField(forms.DecimalField):
    def to_python(self, value):
        return super().to_python(en_digits(str(value or "")).replace("٫", ".").replace("٬", "").replace(",", ""))


class PriceChangeForm(StyledFormMixin, forms.Form):
    MODES = [("percent", "درصد"), ("amount", "مبلغ ثابت (تومان)")]
    DIRECTIONS = [("up", "افزایش"), ("down", "کاهش")]

    brands = forms.ModelMultipleChoiceField(label="برند", queryset=Brand.objects.none(), required=False,
                                            widget=forms.CheckboxSelectMultiple)
    scents = forms.ModelMultipleChoiceField(label="خانواده رایحه", queryset=ScentFamily.objects.none(),
                                            required=False, widget=forms.CheckboxSelectMultiple)
    collections = forms.ModelMultipleChoiceField(label="کالکشن", queryset=Collection.objects.none(), required=False,
                                                 widget=forms.CheckboxSelectMultiple)
    kind = forms.ChoiceField(label="نوع", choices=[("", "همه")] + list(Kind.choices), required=False)
    active_only = forms.BooleanField(label="فقط محصولات فعال", required=False)
    direction = forms.ChoiceField(label="تغییر", choices=DIRECTIONS, initial="up")
    mode = forms.ChoiceField(label="بر اساس", choices=MODES, initial="percent")
    value = LocalizedDecimalField(label="مقدار", min_value=Decimal("0.01"), max_digits=12, decimal_places=2,
                                  widget=forms.TextInput(attrs={"inputmode": "decimal", "dir": "ltr",
                                                                "placeholder": "مثلاً 15"}))
    rounding = forms.TypedChoiceField(label="گرد کردن قیمت جدید به", choices=ROUNDING, coerce=int, initial=10_000)

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brands"].queryset = Brand.objects.for_store(store)
        self.fields["scents"].queryset = ScentFamily.objects.for_store(store)
        self.fields["collections"].queryset = Collection.objects.for_store(store)

    def clean(self):
        data = super().clean()
        if data.get("mode") == "percent" and data.get("direction") == "down" and data.get("value", 0) >= 100:
            self.add_error("value", "کاهش باید کمتر از ۱۰۰٪ باشد.")
        if data.get("mode") == "percent" and data.get("value", 0) > 500:
            self.add_error("value", "افزایش بیش از ۵۰۰٪ مجاز نیست.")
        return data

    @property
    def rule(self):
        d = self.cleaned_data
        value = d["value"] if d["direction"] == "up" else -d["value"]
        return PriceRule(d["mode"], value, d["rounding"])

    def scope_kwargs(self):
        d = self.cleaned_data
        return {"brands": list(d["brands"]), "scents": list(d["scents"]), "collections": list(d["collections"]),
                "kind": d["kind"], "active_only": d["active_only"]}

    def scope_label(self):
        d = self.cleaned_data
        parts = [", ".join(str(x) for x in d[k]) for k in ("brands", "scents", "collections") if d[k]]
        if d["kind"]:
            parts.append(Kind(d["kind"]).label)
        return " / ".join(parts) or "همه محصولات"


class SaleForm(PriceChangeForm):
    """حراج زمان‌دار روی همان انتخاب محصولات فرم تغییر قیمت."""

    name = forms.CharField(label="عنوان حراج", max_length=100, widget=forms.TextInput(attrs={"placeholder": "حراج پاییزه"}))
    percent = forms.IntegerField(label="درصد تخفیف", min_value=1, max_value=90)
    starts_at = JalaliDateTimeField(label="شروع", required=False, help_text="خالی = از همین حالا")
    ends_at = JalaliDateTimeField(label="پایان", required=False, end_of_day=True, help_text="خالی = تا پایان دستی")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("direction", "mode", "value"):
            del self.fields[name]
        self.fields["rounding"].label = "گرد کردن قیمت حراج به"

    def clean(self):
        data = forms.Form.clean(self)
        start, end = data.get("starts_at"), data.get("ends_at")
        if end and end <= (start or timezone.now()):
            self.add_error("ends_at", "پایان حراج باید بعد از شروع (و در آینده) باشد.")
        return data


class CustomerProfileForm(StyledFormMixin, forms.Form):
    tags = forms.CharField(label="برچسب‌ها", max_length=200, required=False,
                           help_text="با کاما جدا کنید؛ مثلاً همکار، عمده، بدقول")
    note = forms.CharField(label="یادداشت داخلی", required=False, widget=forms.Textarea(attrs={"rows": 4}),
                           help_text="فقط کارکنان می‌بینند")


class CampaignForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="عنوان (برای گزارش)", max_length=100)
    message = forms.CharField(
        label="متن پیامک", max_length=500, widget=forms.Textarea(attrs={"rows": 4}),
        initial="{name} عزیز، دلمان برایتان تنگ شده! با کد {code} تا {percent}٪ تخفیف از {store} خرید کنید:\n{shop_url}",
        help_text="متغیرها: {name} نام مشتری، {store}، {code} و {percent} کد تخفیف، {shop_url} نشانی فروشگاه")
    with_coupon = forms.BooleanField(label="ساخت کد تخفیف برای این پیامک", required=False, initial=True)
    percent = forms.IntegerField(label="درصد تخفیف", min_value=1, max_value=90, initial=10, required=False)
    days = forms.IntegerField(label="مدت اعتبار (روز)", min_value=1, max_value=365, initial=7, required=False)
    opt_out = forms.BooleanField(label="افزودن «لغو۱۱» به انتهای پیام (الزام پیامک تبلیغاتی)", required=False,
                                 initial=True)
    confirm = forms.BooleanField(label="متن را بررسی کردم؛ ارسال شود", required=True)

    def clean(self):
        from apps.notifications import events as E

        data = super().clean()
        try:
            E.validate_text(E.CAMPAIGN, data.get("message", ""))
        except forms.ValidationError as exc:
            self.add_error("message", exc)
        if data.get("with_coupon") and not data.get("percent"):
            self.add_error("percent", "درصد تخفیف را وارد کنید.")
        if not data.get("with_coupon") and "{code}" in data.get("message", ""):
            self.add_error("message", "متن {code} دارد ولی کد تخفیفی ساخته نمی‌شود.")
        return data


class GiftCardForm(StyledFormMixin, forms.Form):
    amount = LocalizedDecimalField(label="مبلغ (تومان)", min_value=Decimal(10_000), max_digits=12, decimal_places=0,
                                   widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr"}))
    count = forms.IntegerField(label="تعداد کارت", min_value=1, max_value=200, initial=1)
    recipient_name = forms.CharField(label="نام گیرنده", max_length=80, required=False)
    recipient_phone = forms.CharField(label="موبایل گیرنده (برای پیامک کد)", max_length=11, required=False,
                                      widget=forms.TextInput(attrs={"dir": "ltr", "inputmode": "numeric"}))
    sender_name = forms.CharField(label="از طرف", max_length=80, required=False)
    message = forms.CharField(label="پیام", max_length=200, required=False)
    expires_at = JalaliDateTimeField(label="انقضا", required=False, end_of_day=True, help_text="خالی = بدون انقضا")

    def clean_recipient_phone(self):
        from apps.core.validators import iran_mobile_validator

        phone = en_digits(self.cleaned_data.get("recipient_phone", ""))
        if phone:
            iran_mobile_validator(phone)
        return phone


class PointsAdjustForm(StyledFormMixin, forms.Form):
    points = forms.IntegerField(label="امتیاز (منفی برای کسر)", min_value=-1_000_000, max_value=1_000_000)
    note = forms.CharField(label="علت", max_length=200)
