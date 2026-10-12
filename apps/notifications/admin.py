from django.contrib import admin, messages

from .models import Campaign, NotificationLog, NotificationRule, NotificationSettings
from .services import ensure_rules, sms_available
from .sms import SMSError, get_provider


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ["store", "sms_enabled", "email_enabled", "otp_login_enabled", "staff_phones"]
    actions = ["send_test_sms", "create_default_messages"]

    @admin.action(description="ارسال پیامک آزمایشی به موبایل مدیران")
    def send_test_sms(self, request, queryset):
        if not sms_available():
            self.message_user(request, "سرویس پیامک تنظیم نشده است: SMS_PROVIDER و SMS_API_KEY را در .env بگذارید.",
                              messages.ERROR)
            return
        provider = get_provider()
        for conf in queryset:
            for phone in conf.staff_phone_list:
                try:
                    provider.send(phone, f"پیامک آزمایشی {conf.store.name}: اتصال سرویس پیامک درست است.")
                    self.message_user(request, f"پیامک آزمایشی به {phone} ارسال شد.")
                except SMSError as exc:
                    self.message_user(request, f"{phone}: {exc}", messages.ERROR)
            if not conf.staff_phone_list:
                self.message_user(request, f"{conf.store}: «موبایل مدیران» خالی است.", messages.WARNING)

    @admin.action(description="ساخت پیام‌های پیش‌فرض (فقط موارد نبود)")
    def create_default_messages(self, request, queryset):
        for conf in queryset:
            ensure_rules(conf.store)
        self.message_user(request, "پیام‌های پیش‌فرض ساخته شد.")


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = ["event", "channel", "audience", "is_active", "sms_template"]
    list_editable = ["is_active"]
    list_filter = ["store", "event", "channel", "audience", "is_active"]
    fieldsets = (
        (None, {"fields": ("store", "event", "channel", "audience", "is_active")}),
        ("پیامک", {"fields": ("text", "sms_template", "template_params"),
                   "description": "پیامک متنی از «متن» ساخته می‌شود. اگر «کد الگو» پر باشد، الگوی تأییدشده "
                                  "پنل پیامک با «متغیرهای الگو» (به همان ترتیب) ارسال می‌شود."}),
        ("ایمیل", {"fields": ("subject",)}),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "event", "channel", "recipient", "status", "attempts", "order", "error"]
    list_filter = ["store", "status", "channel", "event", "created_at"]
    search_fields = ["recipient", "order__number", "message_id"]
    date_hierarchy = "created_at"

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "audience", "status", "sent", "failed", "created_at"]
    list_filter = ["store", "status"]
    readonly_fields = [f.name for f in Campaign._meta.fields]

    def has_add_permission(self, request):
        return False  # از استودیو ← مشتریان ← پیامک به این گروه
