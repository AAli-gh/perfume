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
    list_display = ["store", "theme", "preset", "status", "updated_at", "published_at"]
    list_filter = ["store", "status", "theme"]
