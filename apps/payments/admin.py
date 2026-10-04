from django.contrib import admin

from apps.orders.admin import OrderAdmin

from .gateways import registered_codes
from .models import GatewayAccount, Payment


@admin.register(GatewayAccount)
class GatewayAccountAdmin(admin.ModelAdmin):
    list_display = ["title", "gateway", "store", "is_active", "sandbox", "priority"]
    list_filter = ["store", "gateway", "is_active"]
    list_editable = ["is_active", "priority"]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "gateway":
            from django import forms

            choices = [(c, c) for c in registered_codes() if c != "test"]
            return forms.ChoiceField(choices=choices, label=db_field.verbose_name)
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class ReadOnlyPaymentMixin:
    readonly_fields = ["order", "gateway", "amount", "status", "authority", "ref_id", "card_pan", "message", "raw",
                       "created_at", "updated_at", "verified_at"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(ReadOnlyPaymentMixin, admin.ModelAdmin):
    list_display = ["created_at", "order", "gateway", "amount", "status", "ref_id"]
    list_filter = ["status", "gateway", "order__store"]
    search_fields = ["order__number", "authority", "ref_id"]


class PaymentInline(ReadOnlyPaymentMixin, admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["created_at", "gateway", "amount", "status", "ref_id", "message"]


# نمایش پرداخت‌ها داخل صفحه سفارش، بدون اینکه اپ orders به payments وابسته شود
OrderAdmin.inlines = [*OrderAdmin.inlines, PaymentInline]
