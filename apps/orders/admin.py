from django.contrib import admin

from apps.core.jalali import JalaliAdminMixin, to_jalali_text

from django import forms

from .models import CustomerProfile, ReturnItem, ReturnRequest, Order, OrderItem, OrderStatusHistory
from .workflow import allowed_transitions, can_transition, transition


class OrderAdminForm(forms.ModelForm):
    def clean_status(self):
        new = self.cleaned_data["status"]
        old = self.initial.get("status")
        if self.instance.pk and old and not can_transition(old, new):
            allowed = "، ".join(Order.Status(s).label for s in allowed_transitions(old)) or "هیچ"
            raise forms.ValidationError(f"از این وضعیت فقط به این وضعیت‌ها می‌توان رفت: {allowed}")
        return new


class HistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "changed_by", "note", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["variant", "product_name", "size_ml", "unit_price", "quantity"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(JalaliAdminMixin, admin.ModelAdmin):
    list_display = ["number", "full_name", "phone", "total", "payment_method", "status", "created_jalali"]
    list_filter = ["store", "status", "payment_method", "packaging", "created_at"]
    list_editable = ["status"]
    search_fields = ["number", "first_name", "last_name", "phone", "email", "payments__ref_id", "tracking_code"]
    readonly_fields = [
        "number", "store", "user", "subtotal", "discount", "shipping", "total", "coupon_code",
        "points_used", "points_amount", "gift_card_code", "gift_card_amount",
        "paid_at", "created_at", "reserved_until", "inventory_released", "shipping_method_name", "shipped_at",
    ]
    inlines = [OrderItemInline, HistoryInline]

    @admin.display(description="تاریخ ثبت", ordering="created_at")
    def created_jalali(self, obj):
        return to_jalali_text(obj.created_at)
    date_hierarchy = "created_at"
    fieldsets = (
        (None, {"fields": ("number", "store", "user", "status", "payment_method", "created_at")}),
        ("گیرنده", {"fields": ("first_name", "last_name", "phone", "email", "province", "city", "address", "postal_code", "note")}),
        ("مبالغ", {"fields": ("subtotal", "discount", "coupon_code", "shipping", "points_used", "points_amount",
                             "gift_card_code", "gift_card_amount", "total")}),
        ("ارسال", {"fields": ("shipping_method_name", "tracking_code", "shipped_at")}),
        ("بسته‌بندی هدیه", {"fields": ("packaging", "packaging_note", "gift_message", "gift_from", "hide_prices")}),
        ("پرداخت", {"fields": ("paid_at", "reserved_until", "inventory_released")}),
    )

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = OrderAdminForm
        return super().get_form(request, obj, **kwargs)

    def get_changelist_form(self, request, **kwargs):
        kwargs["form"] = OrderAdminForm
        return super().get_changelist_form(request, **kwargs)

    def save_model(self, request, obj, form, change):
        new_status = obj.status
        if change and "status" in form.changed_data:
            obj.status = form.initial["status"]  # تغییر وضعیت فقط از مسیر workflow
            super().save_model(request, obj, form, change)
            transition(obj, new_status, by=request.user, note="تغییر از پنل مدیریت")
        else:
            super().save_model(request, obj, form, change)

    @admin.display(description="نام گیرنده")
    def full_name(self, obj):
        return obj.full_name


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ["phone", "tags", "updated_at", "updated_by"]
    list_filter = ["store"]
    search_fields = ["phone", "tags", "note"]
    readonly_fields = ["updated_by", "updated_at"]


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0
    readonly_fields = ["order_item", "quantity"]
    can_delete = False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ["order", "kind", "status", "reason", "refund_amount", "created_at"]
    list_filter = ["kind", "status", "reason"]
    search_fields = ["order__number", "order__phone"]
    readonly_fields = ["order", "kind", "status", "reason", "description", "by_customer", "refund_amount",
                       "refund_method", "refund_reference", "restocked", "handled_by", "created_at", "refunded_at"]
    inlines = [ReturnItemInline]

    def has_add_permission(self, request):
        return False  # از استودیو ← سفارش‌ها ← مرجوعی / لغو بخشی (برگشت موجودی و مبلغ از سرویس)
