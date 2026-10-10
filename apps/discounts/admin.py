from django.contrib import admin

from apps.core.jalali import JalaliAdminMixin

from .models import Coupon, GiftCard, GiftCardTransaction, LoyaltyAccount, LoyaltyEntry


@admin.register(Coupon)
class CouponAdmin(JalaliAdminMixin, admin.ModelAdmin):
    list_display = ["code", "percent", "max_discount", "min_subtotal", "used_count", "usage_limit", "valid_to", "is_active"]
    list_filter = ["store", "is_active"]
    search_fields = ["code"]


class GiftCardTransactionInline(admin.TabularInline):
    model = GiftCardTransaction
    extra = 0
    readonly_fields = ["amount", "order_number", "note", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(GiftCard)
class GiftCardAdmin(JalaliAdminMixin, admin.ModelAdmin):
    list_display = ["code", "balance", "initial_amount", "source", "is_active", "expires_at", "created_at"]
    list_filter = ["store", "source", "is_active"]
    search_fields = ["code", "recipient_phone", "order_number"]
    readonly_fields = ["initial_amount", "balance", "source", "order_number", "created_at"]
    inlines = [GiftCardTransactionInline]

    def has_add_permission(self, request):
        return False  # صدور از استودیو ← کارت هدیه (با ثبت گردش)


class LoyaltyEntryInline(admin.TabularInline):
    model = LoyaltyEntry
    extra = 0
    readonly_fields = ["points", "reason", "order_number", "note", "created_by", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "points"]
    list_filter = ["store"]
    search_fields = ["user__email", "user__phone"]
    readonly_fields = ["store", "user", "points"]
    inlines = [LoyaltyEntryInline]

    def has_add_permission(self, request):
        return False
