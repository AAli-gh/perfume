from django import forms



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
    category = forms.CharField(required=False)
    min_price = forms.IntegerField(required=False, min_value=0)
    max_price = forms.IntegerField(required=False, min_value=0)
    sort = forms.ChoiceField(required=False, choices=SORTS)

    def __init__(self, *args, brands=(), scents=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].choices = [(b.slug, b.name) for b in brands]
        self.fields["scent"].choices = [(s.slug, s.name) for s in scents]
