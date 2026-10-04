from django import forms

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
