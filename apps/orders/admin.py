from django.contrib import admin

from .models import Order, OrderItem
from .services import change_status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["variant", "product_name", "size_ml", "unit_price", "quantity"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "full_name", "phone", "total", "payment_method", "status", "created_at"]
    list_filter = ["store", "status", "payment_method", "created_at"]
    list_editable = ["status"]
    search_fields = ["number", "first_name", "last_name", "phone", "email", "payment_ref_id"]
    readonly_fields = [
        "number", "store", "user", "subtotal", "discount", "shipping", "total", "coupon_code",
        "payment_authority", "payment_ref_id", "paid_at", "created_at",
    ]
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    fieldsets = (
        (None, {"fields": ("number", "store", "user", "status", "payment_method", "created_at")}),
        ("گیرنده", {"fields": ("first_name", "last_name", "phone", "email", "province", "city", "address", "postal_code", "note")}),
        ("مبالغ", {"fields": ("subtotal", "discount", "coupon_code", "shipping", "total")}),
        ("پرداخت", {"fields": ("payment_authority", "payment_ref_id", "paid_at")}),
    )

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            change_status(obj, obj.status)
        super().save_model(request, obj, form, change)

    @admin.display(description="نام گیرنده")
    def full_name(self, obj):
        return obj.full_name
