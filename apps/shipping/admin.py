from django import forms
from django.contrib import admin

from apps.core.geo import PROVINCE_CHOICES

from .carriers import carrier_choices
from .models import ProvinceRate, ShippingMethod


class ShippingMethodForm(forms.ModelForm):
    carrier = forms.ChoiceField(label="شرکت حمل / اتصال", choices=carrier_choices)
    provinces = forms.MultipleChoiceField(
        label="فقط این استان‌ها", choices=PROVINCE_CHOICES, required=False, widget=forms.CheckboxSelectMultiple,
        help_text="هیچ‌کدام = همه استان‌ها",
    )

    class Meta:
        model = ShippingMethod
        fields = "__all__"
        widgets = {"api_key": forms.PasswordInput(render_value=True), "api_secret": forms.PasswordInput(render_value=True)}


class ProvinceRateInline(admin.TabularInline):
    model = ProvinceRate
    extra = 0


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    form = ShippingMethodForm
    list_display = ["name", "carrier", "cost", "free_over", "is_active", "priority"]
    list_editable = ["is_active", "priority"]
    list_filter = ["store", "is_active", "carrier"]
    inlines = [ProvinceRateInline]
    fieldsets = (
        (None, {"fields": ("store", "name", "description", "is_active", "priority")}),
        ("هزینه", {"fields": ("cost", "free_over", "provinces")}),
        ("شرکت حمل", {"fields": ("carrier", "tracking_url_template", "api_key", "api_secret", "account_id"),
                      "description": "برای ارسال دستی فقط «الگوی پیوند پیگیری» لازم است. اعتبارنامه‌ها فقط برای اتصال API."}),
    )
