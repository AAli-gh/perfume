from django.contrib import admin

from .models import AuditLog, Store, StoreDomain, StoreSettings

admin.site.site_header = "مدیریت عطر مجد"
admin.site.site_title = "عطر مجد"
admin.site.index_title = "پنل مدیریت فروشگاه"


class StoreSettingsInline(admin.StackedInline):
    model = StoreSettings
    can_delete = False
    fieldsets = (
        ("اطلاعات تماس", {"fields": ("tagline", "email", "phone", "phone_link", "address")}),
        ("شبکه‌های اجتماعی", {"fields": ("instagram_url", "telegram_url", "whatsapp_url")}),
        ("فروش و ارسال", {"fields": ("currency_label", "shipping_cost", "free_shipping_over", "payment_timeout_minutes")}),
        ("پرداخت کارت به کارت", {"fields": ("bank_card_number", "bank_card_holder")}),
        ("سئو و شبکه‌های اجتماعی", {"fields": (
            "meta_description", "og_image", "twitter_handle", "google_site_verification", "bing_site_verification",
            "currency_code", "currency_factor",
        )}),
    )


class StoreDomainInline(admin.TabularInline):
    model = StoreDomain
    extra = 0


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_default", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "code", "domains__domain"]
    prepopulated_fields = {"code": ["name"]}
    inlines = [StoreSettingsInline, StoreDomainInline]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """گزارش رویدادهای امنیتی: فقط‌خواندنی و غیرقابل حذف از پنل (پاک‌سازی دوره‌ای خودکار است)."""

    list_display = ["created_at", "action", "user", "target", "ip", "store"]
    list_filter = ["action", "store"]
    search_fields = ["target", "ip", "user__email"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
