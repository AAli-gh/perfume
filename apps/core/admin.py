from django.contrib import admin

from .models import ContactMessage, NewsletterSubscriber

admin.site.site_header = "مدیریت عطر مجد"
admin.site.site_title = "عطر مجد"
admin.site.index_title = "پنل مدیریت فروشگاه"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "subject", "is_read", "created_at"]
    list_filter = ["is_read", "subject"]
    list_editable = ["is_read"]
    search_fields = ["name", "email", "message"]
    readonly_fields = ["name", "email", "subject", "message", "created_at"]


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "created_at"]
    search_fields = ["email"]
