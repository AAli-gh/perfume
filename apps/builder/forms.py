"""فرم‌های استودیو. همه فرم‌ها از schemaهای موجود ساخته می‌شوند (توکن‌ها، هدر/فوتر، انواع بخش)،
پس اعتبارسنجی یک‌جا تعریف شده و فرم و ذخیره‌سازی هیچ‌وقت از هم جدا نمی‌شوند."""

from django import forms

from apps.core.forms import StyledFormMixin
from apps.core.validators import validate_image_upload
from apps.pages import sections
from apps.themes import chrome
from apps.themes import tokens as T

VARIANT_LABELS = {
    "gradient": "گرادیان", "solid": "یکدست", "outline": "دورخط", "flat": "ساده",
    "blur": "شیشه‌ای (محو)", "glow": "درخشش ملایم", "plain": "ساده", "noise": "بافت دانه‌ای",
    "none": "بدون", "strong": "پررنگ", "soft": "ملایم",
}


class StudioFormMixin(StyledFormMixin):
    """کلاس input برای همه ویجت‌ها + ویجت مخصوص رنگ."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 3)


# ---------- پوسته و پیش‌تنظیم ----------

class PresetForm(forms.Form):
    preset = forms.ModelChoiceField(queryset=None, label="پیش‌تنظیم", empty_label=None, widget=forms.RadioSelect)

    def __init__(self, *args, theme, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preset"].queryset = theme.presets.all()


class ThemeChoiceForm(StudioFormMixin, forms.Form):
    theme = forms.ModelChoiceField(queryset=None, label="پوسته", empty_label=None)

    def __init__(self, *args, **kwargs):
        from apps.themes.models import Theme

        super().__init__(*args, **kwargs)
        self.fields["theme"].queryset = Theme.objects.filter(is_available=True)


# ---------- توکن‌ها ----------

def color_field_name(name):
    return f"color__{name}"


class ColorsForm(StudioFormMixin, forms.Form):
    """یک ورودی رنگ برای هر توکن رنگ، گروه‌بندی‌شده مثل COLORS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (default, label, _group) in T.COLORS.items():
            self.fields[color_field_name(name)] = forms.RegexField(
                regex=T.HEX, label=label, initial=default, max_length=7,
                error_messages={"invalid": "رنگ باید به شکل #RRGGBB باشد"},
                widget=forms.TextInput(attrs={"type": "color", "data-token": name, "class": "color-input"}),
            )

    def groups(self):
        out = {}
        for name, (_default, _label, group) in T.COLORS.items():
            out.setdefault(group, []).append(self[color_field_name(name)])
        return list(out.items())

    def to_tokens(self):
        return {"colors": {name: self.cleaned_data[color_field_name(name)].lower() for name in T.COLORS}}

    @staticmethod
    def initial_from(tokens):
        return {color_field_name(name): value for name, value in tokens["colors"].items()}


class TypographyForm(StudioFormMixin, forms.Form):
    font_display = forms.ChoiceField(label="فونت تیترها", choices=[(f, f) for f in T.FONTS])
    font_body = forms.ChoiceField(label="فونت متن", choices=[(f, f) for f in T.FONTS])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for path, (default, lo, hi, label) in T.SIZES.items():
            self.fields[path.replace(".", "__")] = forms.IntegerField(
                label=label, initial=default, min_value=lo, max_value=hi,
                widget=forms.NumberInput(attrs={"class": "input", "dir": "ltr"}),
            )

    def to_tokens(self):
        data = self.cleaned_data
        out = {"typography": {"font_display": data["font_display"], "font_body": data["font_body"]}}
        for path in T.SIZES:
            group, key = path.split(".")
            out.setdefault(group, {})[key] = data[path.replace(".", "__")]
        return out

    @staticmethod
    def initial_from(tokens):
        initial = {"font_display": tokens["typography"]["font_display"], "font_body": tokens["typography"]["font_body"]}
        for path in T.SIZES:
            group, key = path.split(".")
            initial[path.replace(".", "__")] = tokens[group][key]
        return initial


class ComponentsForm(StudioFormMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (default, options, label) in T.COMPONENTS.items():
            self.fields[name] = forms.ChoiceField(
                label=label, initial=default, choices=[(o, VARIANT_LABELS.get(o, o)) for o in options],
            )

    def to_tokens(self):
        return {"components": {name: self.cleaned_data[name] for name in T.COMPONENTS}}

    @staticmethod
    def initial_from(tokens):
        return dict(tokens["components"])


# ---------- لوگو و نماد ----------

class BrandingForm(StudioFormMixin, forms.Form):
    logo = forms.ImageField(label="لوگو", required=False, help_text="PNG، JPG یا WebP — حداکثر ۲ مگابایت",
                            validators=[lambda f: validate_image_upload(f, max_mb=2)])
    clear_logo = forms.BooleanField(label="حذف لوگو (نمایش نام فروشگاه)", required=False)
    favicon = forms.ImageField(label="فاوآیکون", required=False, help_text="مربعی، PNG یا WebP — حداکثر ۲۰۰ کیلوبایت",
                               validators=[lambda f: validate_image_upload(f, max_mb=0.2, extensions=("png", "webp"))])
    clear_favicon = forms.BooleanField(label="حذف فاوآیکون (نماد خودکار)", required=False)
    logo_height = chrome.HeaderForm.base_fields["logo_height"]
    monogram = chrome.HeaderForm.base_fields["monogram"]

    def chrome_values(self):
        return {"logo_height": self.cleaned_data["logo_height"], "monogram": self.cleaned_data["monogram"]}


# ---------- هدر و فوتر ----------

class HeaderEditForm(StudioFormMixin, chrome.HeaderForm):
    """همه فیلدهای هدر به‌جز آن‌هایی که در «لوگو و نماد» ویرایش می‌شوند."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["logo_height"], self.fields["monogram"]


class FooterEditForm(StudioFormMixin, chrome.FooterForm):
    pass


# ---------- بخش‌های صفحه ----------

class AddSectionForm(StudioFormMixin, forms.Form):
    type = forms.ChoiceField(label="نوع بخش", choices=sections.choices)


def section_settings_form(section_type, *args, **kwargs):
    """فرم تنظیمات یک نوع بخش با ظاهر استودیو."""
    form_class = type(f"Studio{section_type.form_class.__name__}", (StudioFormMixin, section_type.form_class), {})
    return form_class(*args, **kwargs)


class SectionImageForm(StudioFormMixin, forms.Form):
    image = forms.ImageField(label="تصویر اختصاصی", required=False,
                             help_text="به‌جای تصویر پوسته — JPG، PNG یا WebP، حداکثر ۳ مگابایت",
                             validators=[validate_image_upload])
    clear_image = forms.BooleanField(label="حذف تصویر اختصاصی (بازگشت به تصویر پوسته)", required=False)
