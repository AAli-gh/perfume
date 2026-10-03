from django import forms
from django.contrib import admin

from . import sections
from .models import ContactMessage, Page, PageSection


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "subject", "is_read", "created_at"]
    list_filter = ["store", "is_read", "subject"]
    list_editable = ["is_read"]
    search_fields = ["name", "email", "message"]
    readonly_fields = ["name", "email", "subject", "message", "created_at"]


class PageSectionForm(forms.ModelForm):
    type = forms.ChoiceField(label="نوع بخش", choices=sections.choices)

    class Meta:
        model = PageSection
        fields = ["type", "order", "is_enabled", "status", "settings", "image"]
        help_texts = {"settings": "خالی بگذارید تا تنظیمات پیش‌فرض این نوع بخش استفاده شود."}


class PageSectionInline(admin.StackedInline):
    """فقط نمایش. بخش‌ها از استودیو (پیش‌نویس ← پیش‌نمایش ← انتشار) ویرایش می‌شوند."""

    model = PageSection
    form = PageSectionForm
    extra = 0
    ordering = ["status", "order", "id"]
    verbose_name_plural = "بخش‌های صفحه (ویرایش از استودیو: /studio/)"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "store", "is_home", "updated_at"]
    list_filter = ["store", "is_home"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [PageSectionInline]
