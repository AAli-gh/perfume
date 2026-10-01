from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "subject", "is_read", "created_at"]
    list_filter = ["store", "is_read", "subject"]
    list_editable = ["is_read"]
    search_fields = ["name", "email", "message"]
    readonly_fields = ["name", "email", "subject", "message", "created_at"]
