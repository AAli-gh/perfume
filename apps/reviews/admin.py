from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["name", "product", "rating", "is_approved", "created_at"]
    list_filter = ["is_approved", "rating"]
    list_editable = ["is_approved"]
    search_fields = ["name", "text", "product__name"]
    actions = ["approve"]

    @admin.action(description="تأیید نظرات انتخاب‌شده")
    def approve(self, request, queryset):
        queryset.update(is_approved=True)
