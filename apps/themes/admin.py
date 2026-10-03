from django.contrib import admin

from .models import Theme, ThemePreset, ThemeSettings


class PresetInline(admin.TabularInline):
    model = ThemePreset
    extra = 0
    fields = ["code", "name", "is_default", "order"]


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "version", "is_available"]
    readonly_fields = ["code", "version", "manifest"]
    inlines = [PresetInline]

    def has_add_permission(self, request):
        return False  # پوسته‌ها از روی دیسک ثبت می‌شوند: python manage.py sync_themes


@admin.register(ThemeSettings)
class ThemeSettingsAdmin(admin.ModelAdmin):
    """نسخه منتشرشده فقط از راه «انتشار» در استودیو تغییر می‌کند (تا پیش‌نویس و تاریخچه دور زده نشوند)."""

    list_display = ["store", "theme", "preset", "status", "updated_at", "published_at"]
    list_filter = ["store", "status", "theme"]

    def has_add_permission(self, request):
        return False  # نسخه‌ها خودکار ساخته می‌شوند

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status == ThemeSettings.Status.PUBLISHED:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.status == ThemeSettings.Status.PUBLISHED:
            return False
        return super().has_delete_permission(request, obj)
