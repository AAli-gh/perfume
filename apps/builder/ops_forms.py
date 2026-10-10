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
