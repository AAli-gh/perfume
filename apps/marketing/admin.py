from django.contrib import admin

from .models import NewsletterSubscriber


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "created_at"]
    list_filter = ["store"]
    search_fields = ["email"]
