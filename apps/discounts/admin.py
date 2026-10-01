from django.contrib import admin

from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "percent", "max_discount", "min_subtotal", "used_count", "usage_limit", "valid_to", "is_active"]
    list_filter = ["store", "is_active"]
    search_fields = ["code"]
